from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import get_type_hints
from uuid import UUID

from django.test import SimpleTestCase

from apps.payments.services.dtos import (
    CreatePlategaInvoiceIn,
    CreatePlategaInvoiceOut,
    PlategaTransactionDTO,
)


class TestPlategaDTOs(SimpleTestCase):
    def test_fixed_platega_dtos_preserve_values_and_annotation_schemas(self) -> None:
        transaction = PlategaTransactionDTO(
            transaction_id=UUID("f8ea17f7-33bd-4a76-b2e6-f37d67eb512d"),
            status="PENDING",
            redirect_url="https://pay.platega.example/redirect",
            expires_in=timedelta(minutes=15),
        )
        create_in = CreatePlategaInvoiceIn(
            username="buyer",
            purchase_kind="subscription",
        )
        create_out = CreatePlategaInvoiceOut(
            payment_url="https://pay.platega.example/redirect",
            rub_amount=Decimal("99.00"),
            expires_at=datetime(2026, 8, 8, 12, 15, tzinfo=UTC),
            reused=False,
        )

        self.assertEqual(transaction, PlategaTransactionDTO(**transaction.asdict()))
        self.assertEqual(create_in, CreatePlategaInvoiceIn(**create_in.asdict()))
        self.assertEqual(create_out, CreatePlategaInvoiceOut(**create_out.asdict()))
        self.assertEqual(
            get_type_hints(PlategaTransactionDTO),
            {
                "transaction_id": UUID,
                "status": str,
                "redirect_url": str,
                "expires_in": timedelta,
            },
        )
        self.assertEqual(
            get_type_hints(CreatePlategaInvoiceIn),
            {"username": str, "purchase_kind": str},
        )
        self.assertEqual(
            get_type_hints(CreatePlategaInvoiceOut),
            {
                "payment_url": str,
                "rub_amount": Decimal,
                "expires_at": datetime,
                "reused": bool,
            },
        )
