from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import PaymentIntentStatusEnum
from apps.payments.models import PaymentIntent
from apps.payments.tests.factories import PaymentIntentFactory


class PaymentIntentTest(TestCase):
    def test_generates_unique_256_bit_invoice_payload(self) -> None:
        first = PaymentIntentFactory()
        second = PaymentIntentFactory()

        self.assertNotEqual(first.invoice_payload, second.invoice_payload)
        self.assertGreaterEqual(len(bytes.fromhex(first.invoice_payload)), 32)

    def test_invoice_payload_is_unique(self) -> None:
        intent = PaymentIntentFactory()

        with self.assertRaises(IntegrityError):
            PaymentIntentFactory(invoice_payload=intent.invoice_payload)

    def test_rejects_malformed_invoice_payloads(self) -> None:
        for payload in ("a" * 63, "A" * 64, "g" * 64, "a" * 65):
            with self.subTest(payload=payload):
                intent = PaymentIntentFactory()
                intent.invoice_payload = payload
                with self.assertRaises(ValidationError):
                    intent.full_clean()

    def test_database_rejects_malformed_invoice_payload(self) -> None:
        with self.assertRaises(IntegrityError):
            PaymentIntentFactory(invoice_payload="not-a-256-bit-token")

    def test_rejects_non_positive_minor_unit_amount(self) -> None:
        intent = PaymentIntentFactory()
        intent.amount = 0

        with self.assertRaises(ValidationError):
            intent.full_clean()

    def test_created_intent_expires_after_ttl(self) -> None:
        intent = PaymentIntentFactory(expires_at=timezone.now() - timedelta(seconds=1))

        self.assertTrue(intent.is_expired)
        self.assertFalse(intent.accepts_successful_payment)

    def test_approved_intent_accepts_payment_after_ttl(self) -> None:
        intent = PaymentIntentFactory(
            status=PaymentIntentStatusEnum.APPROVED,
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        self.assertFalse(intent.is_expired)
        self.assertTrue(intent.accepts_successful_payment)

    def test_paid_intent_does_not_accept_another_payment(self) -> None:
        intent = PaymentIntentFactory(status=PaymentIntentStatusEnum.PAID)

        self.assertFalse(intent.accepts_successful_payment)

    def test_rejects_invalid_state_transition(self) -> None:
        intent = PaymentIntentFactory(status=PaymentIntentStatusEnum.CREATED)

        with self.assertRaises(ValidationError):
            intent.transition_to(status=PaymentIntentStatusEnum.PAID)

    def test_allows_created_approved_paid_state_machine(self) -> None:
        intent = PaymentIntentFactory(status=PaymentIntentStatusEnum.CREATED)

        intent.transition_to(status=PaymentIntentStatusEnum.APPROVED)
        intent.transition_to(status=PaymentIntentStatusEnum.PAID)

        self.assertEqual(intent.status, PaymentIntentStatusEnum.PAID)

    def test_commercial_and_provider_fields_are_immutable(self) -> None:
        intent = PaymentIntentFactory()
        immutable_fields = {
            "user_id": PaymentIntentFactory().user_id,
            "product_id": PaymentIntentFactory().product_id,
            "invoice_payload": "replacement",
            "currency": "XTR",
            "amount": intent.amount + 1,
            "provider": "stars",
            "expires_at": intent.expires_at + timedelta(minutes=1),
        }

        for field, value in immutable_fields.items():
            with self.subTest(field=field):
                current = PaymentIntent.objects.get(pk=intent.pk)
                setattr(current, field, value)
                with self.assertRaises(ValidationError):
                    current.save()

    def test_queryset_update_cannot_bypass_immutability(self) -> None:
        intent = PaymentIntentFactory()

        with self.assertRaises(ValidationError):
            PaymentIntent.objects.filter(pk=intent.pk).update(amount=intent.amount + 1)

    def test_bulk_update_cannot_bypass_immutability(self) -> None:
        intent = PaymentIntentFactory()
        intent.amount += 1

        with self.assertRaises(ValidationError):
            PaymentIntent.objects.bulk_update([intent], fields=("amount",))

    def test_direct_status_write_cannot_bypass_state_machine(self) -> None:
        intent = PaymentIntentFactory(status=PaymentIntentStatusEnum.CREATED)

        with self.assertRaises(ValidationError):
            PaymentIntent.objects.filter(pk=intent.pk).update(
                status=PaymentIntentStatusEnum.PAID,
            )

    def test_model_save_cannot_bypass_state_machine(self) -> None:
        intent = PaymentIntentFactory(status=PaymentIntentStatusEnum.CREATED)
        intent.status = PaymentIntentStatusEnum.PAID

        with self.assertRaises(ValidationError):
            intent.save()

    def test_bulk_update_cannot_bypass_state_machine(self) -> None:
        intent = PaymentIntentFactory(status=PaymentIntentStatusEnum.CREATED)
        intent.status = PaymentIntentStatusEnum.PAID

        with self.assertRaises(ValidationError):
            PaymentIntent.objects.bulk_update([intent], fields=("status",))
