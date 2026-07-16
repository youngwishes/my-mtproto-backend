from __future__ import annotations

from apps.payments.services.dtos import PaymentReceiptData
from apps.payments.tests.factories import PaymentReceiptFactory
from django.test import TestCase


class PaymentReceiptDataTest(TestCase):
    def test_exact_retry_matches_existing_receipt(self) -> None:
        receipt = PaymentReceiptFactory()
        data = PaymentReceiptData(
            intent_id=receipt.intent_id,
            user_id=receipt.user_id,
            product_id=receipt.product_id,
            provider=receipt.provider,
            charge_id=receipt.charge_id,
            currency=receipt.currency,
            amount=receipt.amount,
        )

        self.assertTrue(data.matches(receipt=receipt))

    def test_same_identity_with_different_immutable_data_is_conflict(self) -> None:
        receipt = PaymentReceiptFactory()
        data = PaymentReceiptData(
            intent_id=receipt.intent_id,
            user_id=receipt.user_id,
            product_id=receipt.product_id,
            provider=receipt.provider,
            charge_id=receipt.charge_id,
            currency=receipt.currency,
            amount=receipt.amount + 1,
        )

        self.assertFalse(data.matches(receipt=receipt))
