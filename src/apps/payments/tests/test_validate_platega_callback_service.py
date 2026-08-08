from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest import mock
from uuid import UUID, uuid4

from django.test import TestCase

from apps.payments.enums import PlategaPaymentIntentStatusEnum
from apps.payments.services.dtos import PlategaCallbackDTO
from apps.payments.services.validate_platega_callback import (
    ValidatePlategaCallbackService,
)
from apps.payments.tests.factories import PlategaPaymentIntentFactory


class TestValidatePlategaCallbackService(TestCase):
    now = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)

    def setUp(self) -> None:
        self.service = ValidatePlategaCallbackService(clock=lambda: self.now)

    def _callback(
        self,
        *,
        transaction_id: UUID,
        amount: Decimal = Decimal("99.00"),
        currency: str = "RUB",
        status: str = "CONFIRMED",
        payment_method: int = 2,
    ) -> PlategaCallbackDTO:
        return PlategaCallbackDTO(
            transaction_id=transaction_id,
            amount=amount,
            currency=currency,
            status=status,
            payment_method=payment_method,
        )

    @mock.patch("requests.get")
    def test_unknown_transaction_returns_only_safe_warning_fields(
        self,
        provider_get: mock.Mock,
    ) -> None:
        transaction_id = uuid4()

        result = self.service(callback=self._callback(transaction_id=transaction_id))

        self.assertIsNone(result.payment)
        self.assertEqual(result.reason_code, "unknown_transaction")
        self.assertEqual(
            result.warning.asdict(),
            {
                "reason_code": "unknown_transaction",
                "intent_id": None,
                "provider_transaction_id": transaction_id,
            },
        )
        provider_get.assert_not_called()

    def test_currency_and_method_mismatches_never_change_state(self) -> None:
        transaction_id = uuid4()
        intent = PlategaPaymentIntentFactory(
            status=PlategaPaymentIntentStatusEnum.ACTIVE,
            provider_transaction_id=transaction_id,
        )
        callbacks = (
            self._callback(transaction_id=transaction_id, currency="USD"),
            self._callback(transaction_id=transaction_id, payment_method=3),
        )

        for callback in callbacks:
            with self.subTest(callback=callback):
                result = self.service(callback=callback)
                intent.refresh_from_db()
                self.assertIsNone(result.payment)
                self.assertEqual(result.reason_code, "callback_mismatch")
                self.assertEqual(
                    result.warning.asdict(),
                    {
                        "reason_code": "callback_mismatch",
                        "intent_id": intent.pk,
                        "provider_transaction_id": transaction_id,
                    },
                )
                self.assertEqual(intent.status, PlategaPaymentIntentStatusEnum.ACTIVE)

    def test_confirmed_amount_at_or_above_saved_is_valid_without_rounding(
        self,
    ) -> None:
        accepted_amounts = (
            Decimal("99"),
            Decimal("99.0036"),
            Decimal("999999999999999999999999.12345678901234567890123456789"),
        )
        for amount in accepted_amounts:
            with self.subTest(amount=amount):
                transaction_id = uuid4()
                intent = PlategaPaymentIntentFactory(
                    status=PlategaPaymentIntentStatusEnum.ACTIVE,
                    provider_transaction_id=transaction_id,
                    rub_amount=Decimal("99.00"),
                )

                result = self.service(
                    callback=self._callback(
                        transaction_id=transaction_id,
                        amount=amount,
                    )
                )

                self.assertIsNotNone(result.payment)
                self.assertEqual(
                    result.payment.asdict(),  # type: ignore[union-attr]
                    {
                        "intent_id": intent.pk,
                        "transaction_id": transaction_id,
                    },
                )
                self.assertEqual(result.reason_code, "confirmed")
                self.assertIsNone(result.warning)

    def test_precise_underpayment_is_mismatch_without_rounding(self) -> None:
        transaction_id = uuid4()
        intent = PlategaPaymentIntentFactory(
            status=PlategaPaymentIntentStatusEnum.ACTIVE,
            provider_transaction_id=transaction_id,
            rub_amount=Decimal("99.00"),
        )

        result = self.service(
            callback=self._callback(
                transaction_id=transaction_id,
                amount=Decimal("98.999999999999999999"),
            )
        )

        self.assertIsNone(result.payment)
        self.assertEqual(result.reason_code, "callback_mismatch")
        self.assertEqual(
            result.warning.asdict(),
            {
                "reason_code": "callback_mismatch",
                "intent_id": intent.pk,
                "provider_transaction_id": transaction_id,
            },
        )

    def test_unsupported_status_including_chargeback_is_safe_and_non_mutating(self) -> None:
        for status in ("PENDING", "CHARGEBACKED", "REFUNDED"):
            with self.subTest(status=status):
                transaction_id = uuid4()
                intent = PlategaPaymentIntentFactory(
                    status=PlategaPaymentIntentStatusEnum.ACTIVE,
                    provider_transaction_id=transaction_id,
                )

                result = self.service(
                    callback=self._callback(
                        transaction_id=transaction_id,
                        amount=Decimal("98.999999999999999999"),
                        status=status,
                    )
                )

                intent.refresh_from_db()
                self.assertIsNone(result.payment)
                self.assertEqual(result.reason_code, "unsupported_status")
                self.assertEqual(
                    result.warning.asdict(),
                    {
                        "reason_code": "unsupported_status",
                        "intent_id": intent.pk,
                        "provider_transaction_id": transaction_id,
                    },
                )
                self.assertEqual(intent.status, PlategaPaymentIntentStatusEnum.ACTIVE)

    def test_matching_cancellation_releases_only_active_or_local_expired(self) -> None:
        for status in (
            PlategaPaymentIntentStatusEnum.ACTIVE,
            PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED,
        ):
            with self.subTest(status=status):
                transaction_id = uuid4()
                intent = PlategaPaymentIntentFactory(
                    status=status,
                    provider_transaction_id=transaction_id,
                )

                result = self.service(
                    callback=self._callback(
                        transaction_id=transaction_id,
                        status="CANCELED",
                    )
                )

                intent.refresh_from_db()
                self.assertIsNone(result.payment)
                self.assertEqual(result.reason_code, "canceled")
                self.assertIsNone(result.warning)
                self.assertEqual(
                    intent.status,
                    PlategaPaymentIntentStatusEnum.PROVIDER_CANCELED,
                )

    def test_repeated_or_ineligible_cancellation_is_duplicate_without_warning(self) -> None:
        for status in (
            PlategaPaymentIntentStatusEnum.PROVIDER_CANCELED,
            PlategaPaymentIntentStatusEnum.PROCESSING,
            PlategaPaymentIntentStatusEnum.RETRYABLE,
            PlategaPaymentIntentStatusEnum.FULFILLED,
        ):
            with self.subTest(status=status):
                transaction_id = uuid4()
                intent = PlategaPaymentIntentFactory(
                    status=status,
                    provider_transaction_id=transaction_id,
                )

                result = self.service(
                    callback=self._callback(
                        transaction_id=transaction_id,
                        status="CANCELED",
                    )
                )

                intent.refresh_from_db()
                self.assertIsNone(result.payment)
                self.assertEqual(result.reason_code, "duplicate")
                self.assertIsNone(result.warning)
                self.assertEqual(intent.status, status)

    def test_exact_confirmed_is_validated_for_every_eligible_state(self) -> None:
        for status in (
            PlategaPaymentIntentStatusEnum.ACTIVE,
            PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED,
            PlategaPaymentIntentStatusEnum.RETRYABLE,
            PlategaPaymentIntentStatusEnum.PROCESSING,
            PlategaPaymentIntentStatusEnum.FULFILLED,
        ):
            with self.subTest(status=status):
                transaction_id = uuid4()
                intent = PlategaPaymentIntentFactory(
                    status=status,
                    provider_transaction_id=transaction_id,
                )

                result = self.service(
                    callback=self._callback(transaction_id=transaction_id)
                )

                intent.refresh_from_db()
                self.assertEqual(
                    result.payment.asdict(),
                    {
                        "intent_id": intent.pk,
                        "transaction_id": transaction_id,
                    },
                )
                self.assertEqual(result.reason_code, "confirmed")
                self.assertIsNone(result.warning)
                self.assertEqual(intent.status, status)

    def test_confirmed_in_ineligible_state_does_not_fulfill_or_warn(self) -> None:
        transaction_id = uuid4()
        intent = PlategaPaymentIntentFactory(
            status=PlategaPaymentIntentStatusEnum.PROVIDER_CANCELED,
            provider_transaction_id=transaction_id,
        )

        result = self.service(callback=self._callback(transaction_id=transaction_id))

        intent.refresh_from_db()
        self.assertIsNone(result.payment)
        self.assertEqual(result.reason_code, "duplicate")
        self.assertIsNone(result.warning)
        self.assertEqual(
            intent.status,
            PlategaPaymentIntentStatusEnum.PROVIDER_CANCELED,
        )
