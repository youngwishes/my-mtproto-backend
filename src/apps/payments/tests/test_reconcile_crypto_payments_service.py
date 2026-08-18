from __future__ import annotations

from unittest import mock

from django.test import TestCase

from apps.payments.clients import CryptoPayClient
from apps.payments.enums import (
    CryptoPaymentIntentStatusEnum,
    PaymentKindEnum,
    PaymentProviderEnum,
)
from apps.payments.exceptions import CryptoPayClientError, CryptoPaymentRetryable
from apps.payments.services.dtos import ApplyCryptoPaymentOut, ValidatedCryptoPaymentDTO
from apps.payments.tests.factories import (
    AppleCashbackPurchaseFactory,
    CryptoPaymentIntentFactory,
    PaymentFactory,
    make_crypto_invoice,
)
from apps.users.tests.factories import SystemUserFactory


class TestReconcileCryptoPaymentsService(TestCase):
    def setUp(self) -> None:
        from apps.payments.services.reconcile_crypto_payments import (
            ReconcileCryptoPaymentsService,
        )

        self.client = mock.Mock(spec=CryptoPayClient)
        self.validator = mock.Mock()
        self.apply = mock.Mock()
        self.enqueue_notification = mock.Mock()
        self.service = ReconcileCryptoPaymentsService(
            crypto_pay_client=self.client,
            validate_invoice_service=self.validator,
            apply_payment_service=self.apply,
            enqueue_notification=self.enqueue_notification,
        )

    def test_selects_only_unfinished_statuses_in_a_bounded_provider_batch(self) -> None:
        selected = [
            CryptoPaymentIntentFactory(
                status=status,
                provider_invoice_id=1000 + index,
            )
            for index, status in enumerate(
                (
                    CryptoPaymentIntentStatusEnum.ACTIVE,
                    CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
                    CryptoPaymentIntentStatusEnum.RETRYABLE,
                )
            )
        ]
        for index in range(3, 101):
            selected.append(
                CryptoPaymentIntentFactory(
                    status=CryptoPaymentIntentStatusEnum.ACTIVE,
                    provider_invoice_id=1000 + index,
                )
            )
        CryptoPaymentIntentFactory(
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            provider_invoice_id=9999,
        )
        self.client.get_invoices.return_value = []

        counters = self.service()

        self.assertEqual(counters["checked"], 0)
        self.assertEqual(
            len(self.client.get_invoices.call_args.kwargs["invoice_ids"]),
            100,
        )
        self.assertEqual(
            self.client.get_invoices.call_args.kwargs["invoice_ids"],
            [intent.provider_invoice_id for intent in selected[:100]],
        )

    def test_paid_unfinished_uses_same_validator_and_apply(self) -> None:
        intent = CryptoPaymentIntentFactory(
            status=CryptoPaymentIntentStatusEnum.RETRYABLE,
            provider_invoice_id=731,
        )
        paid = make_crypto_invoice(invoice_id=731, status="paid")
        validated = ValidatedCryptoPaymentDTO(intent_id=intent.pk, invoice=paid)
        self.client.get_invoices.return_value = [paid]
        self.validator.return_value = validated
        self.apply.return_value = ApplyCryptoPaymentOut(
            fulfilled=True,
            already_fulfilled=False,
        )

        counters = self.service()

        self.validator.assert_called_once_with(update_id=None, invoice=paid)
        self.apply.assert_called_once_with(payment=validated)
        self.assertEqual(
            counters,
            {
                "checked": 1,
                "paid": 1,
                "fulfilled": 1,
                "provider_expired": 0,
                "retryable_failed": 0,
                "notifications_enqueued": 0,
            },
        )

    def test_active_invoice_keeps_intent_unchanged(self) -> None:
        intent = CryptoPaymentIntentFactory(
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_invoice_id=732,
        )
        self.client.get_invoices.return_value = [
            make_crypto_invoice(invoice_id=732, status="active", paid_at=None)
        ]

        counters = self.service()

        intent.refresh_from_db()
        self.assertEqual(intent.status, CryptoPaymentIntentStatusEnum.ACTIVE)
        self.validator.assert_not_called()
        self.apply.assert_not_called()
        self.assertEqual(counters["checked"], 1)

    def test_expired_invoice_conditionally_marks_provider_expired(self) -> None:
        intent = CryptoPaymentIntentFactory(
            status=CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
            provider_invoice_id=733,
        )
        self.client.get_invoices.return_value = [
            make_crypto_invoice(invoice_id=733, status="expired", paid_at=None)
        ]

        counters = self.service()

        intent.refresh_from_db()
        self.assertEqual(intent.status, CryptoPaymentIntentStatusEnum.PROVIDER_EXPIRED)
        self.assertEqual(counters["provider_expired"], 1)

    def test_per_invoice_failure_does_not_stop_later_paid_invoice(self) -> None:
        failed = CryptoPaymentIntentFactory(
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_invoice_id=734,
        )
        succeeded = CryptoPaymentIntentFactory(
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_invoice_id=735,
        )
        invoices = [
            make_crypto_invoice(invoice_id=failed.provider_invoice_id),
            make_crypto_invoice(invoice_id=succeeded.provider_invoice_id),
        ]
        self.client.get_invoices.return_value = invoices
        self.validator.side_effect = [
            CryptoPaymentRetryable("0", reason_code="invalid"),
            ValidatedCryptoPaymentDTO(intent_id=succeeded.pk, invoice=invoices[1]),
        ]
        self.apply.return_value = ApplyCryptoPaymentOut(
            fulfilled=True,
            already_fulfilled=False,
        )

        counters = self.service()

        self.assertEqual(self.apply.call_count, 1)
        self.assertEqual(counters["retryable_failed"], 1)
        self.assertEqual(counters["fulfilled"], 1)

    def test_global_provider_failure_escapes_for_task_retry(self) -> None:
        CryptoPaymentIntentFactory(
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_invoice_id=736,
        )
        self.client.get_invoices.side_effect = CryptoPayClientError("unavailable")

        with self.assertRaises(CryptoPayClientError):
            self.service()

    def test_unnotified_fulfilled_intent_is_enqueued_once_per_run(self) -> None:
        user = SystemUserFactory()
        payment = PaymentFactory(
            user=user,
            kind=PaymentKindEnum.SUBSCRIPTION,
            provider=PaymentProviderEnum.CRYPTO_PAY,
        )
        AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key=f"crypto_pay:{payment.charge_id}:subscription",
        )
        intent = CryptoPaymentIntentFactory(
            initiator=user,
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            payment=payment,
        )

        counters = self.service()

        self.enqueue_notification.assert_called_once_with(intent_id=intent.pk)
        self.assertEqual(counters["notifications_enqueued"], 1)

    def test_historical_fulfilled_intent_is_not_enqueued(self) -> None:
        user = SystemUserFactory()
        payment = PaymentFactory(
            user=user,
            kind=PaymentKindEnum.SUBSCRIPTION,
            provider=PaymentProviderEnum.CRYPTO_PAY,
        )
        AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key=f"crypto_pay:{payment.charge_id}:subscription",
            rate_percent=None,
            apples_earned=0,
            balance_after=0,
            eligible_purchase_count_after=1,
        )
        CryptoPaymentIntentFactory(
            initiator=user,
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            payment=payment,
        )

        counters = self.service()

        self.enqueue_notification.assert_not_called()
        self.assertEqual(counters["notifications_enqueued"], 0)
