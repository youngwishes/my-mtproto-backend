from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from django.test import TestCase

from apps.payments.enums import CryptoPaymentIntentStatusEnum
from apps.payments.models import Payment
from apps.payments.services.dtos import (
    CryptoWebhookWarningDTO,
    ValidatedCryptoPaymentDTO,
)
from apps.payments.services.validate_crypto_invoice import (
    ValidateCryptoInvoiceService,
)
from apps.payments.tests.factories import (
    CryptoPaymentIntentFactory,
    make_crypto_invoice,
)


class TestValidateCryptoInvoiceService(TestCase):
    expires_at = datetime(2026, 8, 2, 12, 30, tzinfo=UTC)
    public_id = UUID("0f57a4f1-1956-45be-8dc0-d891c00c74c1")

    def setUp(self) -> None:
        self.intent = CryptoPaymentIntentFactory(
            public_id=self.public_id,
            status=CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
            provider_invoice_id=731,
            provider_expires_at=self.expires_at,
        )
        self.valid_invoice = make_crypto_invoice(
            invoice_id=731,
            payload=str(self.public_id),
            expiration_date=self.expires_at,
            paid_at=datetime(2026, 8, 2, 12, 20, tzinfo=UTC),
        )
        self.service = ValidateCryptoInvoiceService()

    def test_unknown_invoice_returns_only_safe_provider_identity(self) -> None:
        invoice = replace(self.valid_invoice, invoice_id=999999)

        result = self.service(update_id=42, invoice=invoice)

        self.assertEqual(
            result,
            CryptoWebhookWarningDTO(
                reason="unknown_invoice",
                update_id=42,
                invoice_id=999999,
                intent_id=None,
            ),
        )
        self.assertEqual(Payment.objects.count(), 0)

    def test_each_mismatch_returns_its_exact_safe_reason(self) -> None:
        cases = (
            ("status", "active", "status_mismatch"),
            ("payload", "wrong-public-id", "payload_mismatch"),
            ("currency_type", "crypto", "fiat_mismatch"),
            ("fiat", "USD", "fiat_mismatch"),
            ("amount", Decimal("98.99"), "amount_mismatch"),
            (
                "accepted_assets",
                frozenset({"USDT"}),
                "accepted_assets_mismatch",
            ),
            ("paid_asset", "BTC", "paid_asset_mismatch"),
            (
                "expiration_date",
                datetime(2026, 8, 2, 12, 31, tzinfo=UTC),
                "expiration_mismatch",
            ),
            ("paid_at", None, "paid_at_mismatch"),
            (
                "paid_at",
                datetime(2026, 8, 2, 12, 31, tzinfo=UTC),
                "paid_at_mismatch",
            ),
        )

        for field, value, reason in cases:
            with self.subTest(field=field):
                invoice = replace(self.valid_invoice, **{field: value})

                result = self.service(update_id=42, invoice=invoice)

                self.assertEqual(
                    result,
                    CryptoWebhookWarningDTO(
                        reason=reason,
                        update_id=42,
                        invoice_id=invoice.invoice_id,
                        intent_id=self.intent.pk,
                    ),
                )
                self.assertEqual(Payment.objects.count(), 0)

    def test_timely_provider_payment_validates_after_local_expiry(self) -> None:
        result = self.service(update_id=42, invoice=self.valid_invoice)

        self.assertEqual(
            result,
            ValidatedCryptoPaymentDTO(
                intent_id=self.intent.pk,
                invoice=self.valid_invoice,
            ),
        )
        self.assertEqual(Payment.objects.count(), 0)
