from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import get_type_hints

from django.test import SimpleTestCase

from apps.payments.services.dtos import (
    ApplyCryptoPaymentOut,
    CreateCryptoInvoiceIn,
    CreateCryptoInvoiceOut,
    CryptoInvoiceDTO,
    CryptoWebhookWarningDTO,
    ValidatedCryptoPaymentDTO,
)
from apps.payments.tests.factories import make_crypto_invoice


class TestCryptoPayDTOs(SimpleTestCase):
    def test_crypto_invoice_dto_preserves_fixed_fields_and_compares_by_value(self) -> None:
        invoice = make_crypto_invoice()

        self.assertEqual(invoice, make_crypto_invoice())
        self.assertEqual(invoice.invoice_id, 731)
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(invoice.currency_type, "fiat")
        self.assertEqual(invoice.fiat, "RUB")
        self.assertEqual(invoice.amount, Decimal("99.00"))
        self.assertEqual(invoice.accepted_assets, frozenset({"USDT", "TON"}))
        self.assertEqual(invoice.paid_asset, "USDT")
        self.assertEqual(invoice.payload, "0f57a4f1-1956-45be-8dc0-d891c00c74c1")
        self.assertEqual(invoice.bot_invoice_url, "https://t.me/CryptoBot?start=test")
        self.assertEqual(invoice.created_at, datetime(2026, 8, 2, 12, 0, tzinfo=UTC))
        self.assertEqual(
            invoice.expiration_date,
            datetime(2026, 8, 2, 12, 30, tzinfo=UTC),
        )
        self.assertEqual(invoice.paid_at, datetime(2026, 8, 2, 12, 20, tzinfo=UTC))

    def test_fixed_crypto_dtos_preserve_their_typed_values(self) -> None:
        invoice = make_crypto_invoice()
        create_in = CreateCryptoInvoiceIn(username="buyer", purchase_kind="subscription")
        create_out = CreateCryptoInvoiceOut(
            invoice_url="https://t.me/CryptoBot?start=test",
            rub_amount=Decimal("99.00"),
            expires_at=datetime(2026, 8, 2, 12, 30, tzinfo=UTC),
            reused=False,
        )
        validated = ValidatedCryptoPaymentDTO(intent_id=11, invoice=invoice)
        warning = CryptoWebhookWarningDTO(
            reason="unknown_invoice",
            update_id=1,
            invoice_id=731,
            intent_id=None,
        )
        applied = ApplyCryptoPaymentOut(fulfilled=True, already_fulfilled=False)

        self.assertEqual(create_in, CreateCryptoInvoiceIn(username="buyer", purchase_kind="subscription"))
        self.assertEqual((create_in.username, create_in.purchase_kind), ("buyer", "subscription"))
        self.assertEqual(create_out, CreateCryptoInvoiceOut(**create_out.asdict()))
        self.assertEqual(
            (create_out.invoice_url, create_out.rub_amount, create_out.expires_at, create_out.reused),
            ("https://t.me/CryptoBot?start=test", Decimal("99.00"), datetime(2026, 8, 2, 12, 30, tzinfo=UTC), False),
        )
        self.assertEqual(validated, ValidatedCryptoPaymentDTO(intent_id=11, invoice=invoice))
        self.assertEqual((validated.intent_id, validated.invoice), (11, invoice))
        self.assertEqual(warning, CryptoWebhookWarningDTO(**warning.asdict()))
        self.assertEqual((warning.reason, warning.update_id, warning.invoice_id, warning.intent_id), ("unknown_invoice", 1, 731, None))
        self.assertEqual(applied, ApplyCryptoPaymentOut(fulfilled=True, already_fulfilled=False))
        self.assertEqual((applied.fulfilled, applied.already_fulfilled), (True, False))

    def test_fixed_crypto_dto_annotation_schemas_do_not_drift(self) -> None:
        expected_schemas = {
            CryptoInvoiceDTO: {"invoice_id": int, "status": str, "currency_type": str, "fiat": str | None, "amount": Decimal, "accepted_assets": frozenset[str], "paid_asset": str | None, "payload": str, "bot_invoice_url": str, "created_at": datetime, "expiration_date": datetime, "paid_at": datetime | None},
            CreateCryptoInvoiceIn: {"username": str, "purchase_kind": str},
            CreateCryptoInvoiceOut: {"invoice_url": str, "rub_amount": Decimal, "expires_at": datetime, "reused": bool},
            ValidatedCryptoPaymentDTO: {"intent_id": int, "invoice": CryptoInvoiceDTO},
            CryptoWebhookWarningDTO: {"reason": str, "update_id": int | None, "invoice_id": int | None, "intent_id": int | None},
            ApplyCryptoPaymentOut: {"fulfilled": bool, "already_fulfilled": bool},
        }

        for dto, expected_schema in expected_schemas.items():
            with self.subTest(dto=dto.__name__):
                self.assertEqual(get_type_hints(dto), expected_schema)
