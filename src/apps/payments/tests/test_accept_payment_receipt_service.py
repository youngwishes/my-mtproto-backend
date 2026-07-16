from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import (
    PaymentIntentStatusEnum,
    PaymentProviderEnum,
    PaymentReceiptStatusEnum,
    ProductCodeEnum,
)
from apps.payments.exceptions import (
    PaymentIdentityConflict,
    PaymentIntentMismatch,
    PaymentIntentNotFound,
)
from apps.payments.models import PaymentIntent, PaymentReceipt
from apps.payments.services.accept_payment_receipt import (
    AcceptPaymentReceiptService,
    get_accept_payment_receipt_service,
)
from apps.payments.services.dtos import AcceptPaymentReceiptIn
from apps.payments.tests.factories import (
    PaymentFactory,
    PaymentIntentFactory,
    PaymentReceiptFactory,
)


class AcceptPaymentReceiptServiceTest(TestCase):
    def setUp(self) -> None:
        self.intent = PaymentIntentFactory(
            user__username="123",
            product__code=ProductCodeEnum.VLESS_30D,
            status=PaymentIntentStatusEnum.APPROVED,
            currency="RUB",
            amount=19_900,
            provider=PaymentProviderEnum.YUKASSA,
        )
        self.schedule_receipt = Mock()
        self.service = get_accept_payment_receipt_service(
            schedule_receipt=self.schedule_receipt
        )
        self.payment = AcceptPaymentReceiptIn(
            username="123",
            invoice_payload=self.intent.invoice_payload,
            provider=PaymentProviderEnum.YUKASSA,
            charge_id="yukassa-charge-1",
            currency="RUB",
            amount=19_900,
        )

    def test_atomically_marks_approved_intent_paid_and_creates_received_receipt(
        self,
    ) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            result = self.service(payment=self.payment)

        self.intent.refresh_from_db()
        receipt = PaymentReceipt.objects.get(pk=result.receipt_id)
        self.assertEqual(self.intent.status, PaymentIntentStatusEnum.PAID)
        self.assertEqual(receipt.intent, self.intent)
        self.assertEqual(receipt.status, PaymentReceiptStatusEnum.RECEIVED)
        self.assertEqual(receipt.user, self.intent.user)
        self.assertEqual(receipt.product, self.intent.product)
        self.assertEqual(receipt.provider, PaymentProviderEnum.YUKASSA)
        self.assertEqual(receipt.charge_id, "yukassa-charge-1")
        self.assertEqual(receipt.currency, "RUB")
        self.assertEqual(receipt.amount, 19_900)
        self.assertFalse(result.is_replay)
        self.schedule_receipt.assert_called_once_with(receipt_id=receipt.pk)

    def test_exact_replay_returns_same_receipt_without_second_schedule(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            first = self.service(payment=self.payment)
            second = self.service(payment=self.payment)

        self.assertEqual(first.receipt_id, second.receipt_id)
        self.assertFalse(first.is_replay)
        self.assertTrue(second.is_replay)
        self.assertEqual(PaymentReceipt.objects.count(), 1)
        self.schedule_receipt.assert_called_once_with(receipt_id=first.receipt_id)

    def test_concurrent_exact_insert_collision_returns_winning_receipt(self) -> None:
        winner = PaymentReceiptFactory(
            intent=self.intent,
            charge_id=self.payment.charge_id,
        )
        get_receipt = Mock(side_effect=(None, winner))
        service = AcceptPaymentReceiptService(
            get_intent=Mock(return_value=self.intent),
            get_receipt=get_receipt,
            get_receipt_by_intent=Mock(),
            get_payment=Mock(return_value=None),
            create_receipt=Mock(side_effect=IntegrityError("unique identity")),
            register_after_commit=Mock(),
            schedule_receipt=Mock(),
        )

        result = service(payment=self.payment)

        self.assertEqual(result.receipt_id, winner.pk)
        self.assertTrue(result.is_replay)

    def test_concurrent_different_charge_one_to_one_collision_is_domain_conflict(
        self,
    ) -> None:
        winner = PaymentReceiptFactory(
            intent=self.intent,
            charge_id="winning-charge",
        )
        service = AcceptPaymentReceiptService(
            get_intent=Mock(return_value=self.intent),
            get_receipt=Mock(return_value=None),
            get_receipt_by_intent=Mock(return_value=winner),
            get_payment=Mock(return_value=None),
            create_receipt=Mock(side_effect=IntegrityError("unique intent_id")),
            register_after_commit=Mock(),
            schedule_receipt=Mock(),
        )

        with self.assertRaises(PaymentIdentityConflict):
            service(payment=self.payment)

    def test_same_charge_with_different_immutable_identity_is_conflict(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            self.service(payment=self.payment)
        other_intent = PaymentIntentFactory(
            user__username="456",
            product=self.intent.product,
            status=PaymentIntentStatusEnum.APPROVED,
            currency="RUB",
            amount=19_900,
            provider=PaymentProviderEnum.YUKASSA,
        )
        conflict = AcceptPaymentReceiptIn(
            username="456",
            invoice_payload=other_intent.invoice_payload,
            provider=PaymentProviderEnum.YUKASSA,
            charge_id=self.payment.charge_id,
            currency="RUB",
            amount=19_900,
        )

        with self.assertRaises(PaymentIdentityConflict):
            self.service(payment=conflict)

        other_intent.refresh_from_db()
        self.assertEqual(other_intent.status, PaymentIntentStatusEnum.APPROVED)
        self.assertEqual(PaymentReceipt.objects.count(), 1)

    def test_rejects_collision_with_existing_legacy_payment(self) -> None:
        PaymentFactory(
            user=self.intent.user,
            product=self.intent.product,
            provider=self.payment.provider,
            charge_id=self.payment.charge_id,
        )

        with self.assertRaises(PaymentIdentityConflict):
            self.service(payment=self.payment)

        self.intent.refresh_from_db()
        self.assertEqual(self.intent.status, PaymentIntentStatusEnum.APPROVED)
        self.assertEqual(PaymentReceipt.objects.count(), 0)

    def test_accepts_approved_intent_after_ttl_elapsed(self) -> None:
        PaymentIntent.objects.filter(pk=self.intent.pk)._safe_update(
            expires_at=timezone.now() - timedelta(days=1)
        )
        self.intent.refresh_from_db()

        result = self.service(payment=self.payment)

        self.assertEqual(
            PaymentReceipt.objects.get(pk=result.receipt_id).status,
            PaymentReceiptStatusEnum.RECEIVED,
        )

    def test_acceptance_has_no_sale_flag_or_node_availability_dependency(self) -> None:
        fields = AcceptPaymentReceiptService.__dataclass_fields__

        self.assertNotIn("check_sale_availability", fields)
        self.assertNotIn("sales_enabled", fields)
        self.service(payment=self.payment)
        self.assertEqual(PaymentReceipt.objects.count(), 1)

    def test_rejects_unknown_or_unapproved_intent(self) -> None:
        missing_service = AcceptPaymentReceiptService(
            get_intent=Mock(return_value=None),
            get_receipt=Mock(return_value=None),
            get_receipt_by_intent=Mock(return_value=None),
            get_payment=Mock(return_value=None),
            create_receipt=PaymentReceipt.objects.create,
            register_after_commit=Mock(),
            schedule_receipt=Mock(),
        )
        with self.assertRaises(PaymentIntentNotFound):
            missing_service(payment=self.payment)

        for status in (
            PaymentIntentStatusEnum.CREATED,
            PaymentIntentStatusEnum.EXPIRED,
            PaymentIntentStatusEnum.CANCELLED,
            PaymentIntentStatusEnum.PAID,
        ):
            with self.subTest(status=status):
                intent = PaymentIntentFactory(
                    user__username=f"user-{status}",
                    product=self.intent.product,
                    status=status,
                    currency="RUB",
                    amount=19_900,
                    provider=PaymentProviderEnum.YUKASSA,
                )
                payment = AcceptPaymentReceiptIn(
                    username=intent.user.username,
                    invoice_payload=intent.invoice_payload,
                    provider=intent.provider,
                    charge_id=f"charge-{status}",
                    currency=intent.currency,
                    amount=intent.amount,
                )
                with self.assertRaises(PaymentIntentMismatch):
                    self.service(payment=payment)

    def test_accepts_exact_stars_identity_and_charge_id(self) -> None:
        intent = PaymentIntentFactory(
            user__username="stars-user",
            product=self.intent.product,
            status=PaymentIntentStatusEnum.APPROVED,
            currency="XTR",
            amount=150,
            provider=PaymentProviderEnum.STARS,
        )
        payment = AcceptPaymentReceiptIn(
            username="stars-user",
            invoice_payload=intent.invoice_payload,
            provider=PaymentProviderEnum.STARS,
            charge_id="telegram-charge-1",
            currency="XTR",
            amount=150,
        )

        result = self.service(payment=payment)

        receipt = PaymentReceipt.objects.get(pk=result.receipt_id)
        self.assertEqual(receipt.provider, PaymentProviderEnum.STARS)
        self.assertEqual(receipt.charge_id, "telegram-charge-1")
        self.assertEqual(receipt.currency, "XTR")
        self.assertEqual(receipt.amount, 150)

    def test_rejects_currency_amount_provider_user_or_product_mismatch(self) -> None:
        mismatches = (
            {"username": "other"},
            {"currency": "XTR"},
            {"amount": 19_901},
            {"provider": PaymentProviderEnum.STARS},
        )
        for index, changes in enumerate(mismatches):
            with self.subTest(changes=changes):
                values = {
                    "username": "123",
                    "invoice_payload": self.intent.invoice_payload,
                    "provider": PaymentProviderEnum.YUKASSA,
                    "charge_id": f"mismatch-{index}",
                    "currency": "RUB",
                    "amount": 19_900,
                    **changes,
                }
                with self.assertRaises(PaymentIntentMismatch):
                    self.service(payment=AcceptPaymentReceiptIn(**values))

        non_vless = PaymentIntentFactory(
            user__username="mtproto-user",
            product__code=ProductCodeEnum.MTPROTO_30D,
            status=PaymentIntentStatusEnum.APPROVED,
        )
        with self.assertRaises(PaymentIntentMismatch):
            self.service(
                payment=AcceptPaymentReceiptIn(
                    username="mtproto-user",
                    invoice_payload=non_vless.invoice_payload,
                    provider=non_vless.provider,
                    charge_id="wrong-product",
                    currency=non_vless.currency,
                    amount=non_vless.amount,
                )
            )

    def test_callback_failure_cannot_erase_received_receipt(self) -> None:
        schedule_receipt = Mock(side_effect=RuntimeError("broker unavailable"))

        def run_immediately(callback: object) -> None:
            callback()

        service = AcceptPaymentReceiptService(
            get_intent=lambda **_: self.intent,
            get_receipt=lambda **_: None,
            get_receipt_by_intent=lambda **_: None,
            get_payment=lambda **_: None,
            create_receipt=PaymentReceipt.objects.create,
            register_after_commit=run_immediately,
            schedule_receipt=schedule_receipt,
        )

        result = service(payment=self.payment)

        self.assertEqual(
            PaymentReceipt.objects.get(pk=result.receipt_id).status,
            PaymentReceiptStatusEnum.RECEIVED,
        )
        self.intent.refresh_from_db()
        self.assertEqual(self.intent.status, PaymentIntentStatusEnum.PAID)

    def test_empty_charge_id_is_bad_payment_identity(self) -> None:
        payment = AcceptPaymentReceiptIn(
            username=self.payment.username,
            invoice_payload=self.payment.invoice_payload,
            provider=self.payment.provider,
            charge_id="",
            currency=self.payment.currency,
            amount=self.payment.amount,
        )

        with self.assertRaises(PaymentIntentMismatch):
            self.service(payment=payment)
