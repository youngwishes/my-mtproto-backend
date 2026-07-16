from __future__ import annotations

import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import PaymentReceiptStatusEnum
from apps.payments.models import PaymentReceipt
from apps.payments.tests.factories import (
    PaymentFactory,
    PaymentIntentFactory,
    PaymentReceiptFactory,
)


class PaymentReceiptTest(TestCase):
    def test_provider_charge_identity_is_unique(self) -> None:
        receipt = PaymentReceiptFactory()

        with self.assertRaises(IntegrityError):
            PaymentReceiptFactory(
                provider=receipt.provider,
                charge_id=receipt.charge_id,
            )

    def test_rejects_empty_charge_id(self) -> None:
        receipt = PaymentReceiptFactory.build(charge_id="")

        with self.assertRaises(ValidationError):
            receipt.full_clean()

    def test_rejects_non_positive_minor_unit_amount(self) -> None:
        receipt = PaymentReceiptFactory()
        receipt.amount = 0

        with self.assertRaises(ValidationError):
            receipt.full_clean()

    def test_intent_has_at_most_one_receipt(self) -> None:
        receipt = PaymentReceiptFactory()

        with self.assertRaises(IntegrityError):
            PaymentReceiptFactory(intent=receipt.intent)

    def test_commercial_and_provider_fields_are_immutable(self) -> None:
        receipt = PaymentReceiptFactory()
        immutable_fields = {
            "intent_id": PaymentIntentFactory().pk,
            "user_id": PaymentIntentFactory().user_id,
            "product_id": PaymentIntentFactory().product_id,
            "provider": "stars",
            "charge_id": "replacement",
            "currency": "XTR",
            "amount": receipt.amount + 1,
            "accepted_at": receipt.accepted_at + timedelta(seconds=1),
        }

        for field, value in immutable_fields.items():
            with self.subTest(field=field):
                current = PaymentReceipt.objects.get(pk=receipt.pk)
                setattr(current, field, value)
                with self.assertRaises(ValidationError):
                    current.save()

    def test_queryset_update_cannot_bypass_immutability(self) -> None:
        receipt = PaymentReceiptFactory()

        with self.assertRaises(ValidationError):
            PaymentReceipt.objects.filter(pk=receipt.pk).update(
                charge_id="replacement",
            )

    def test_bulk_update_cannot_bypass_immutability(self) -> None:
        receipt = PaymentReceiptFactory()
        receipt.amount += 1

        with self.assertRaises(ValidationError):
            PaymentReceipt.objects.bulk_update([receipt], fields=("amount",))

    def test_model_save_cannot_bypass_lease_state(self) -> None:
        receipt = PaymentReceiptFactory()
        receipt.status = PaymentReceiptStatusEnum.PROCESSING
        receipt.lease_id = uuid.uuid4()
        receipt.processing_started_at = timezone.now()

        with self.assertRaises(ValidationError):
            receipt.save()

    def test_bulk_update_cannot_bypass_lease_state(self) -> None:
        receipt = PaymentReceiptFactory()
        receipt.status = PaymentReceiptStatusEnum.PROCESSING
        receipt.lease_id = uuid.uuid4()
        receipt.processing_started_at = timezone.now()

        with self.assertRaises(ValidationError):
            PaymentReceipt.objects.bulk_update(
                [receipt],
                fields=("status", "lease_id", "processing_started_at"),
            )

    def test_retry_state_is_due_at_next_attempt(self) -> None:
        receipt = PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.RETRY,
            next_attempt_at=timezone.now() - timedelta(seconds=1),
        )

        self.assertTrue(receipt.is_ready_for_processing)

    def test_rejects_invalid_state_transition(self) -> None:
        receipt = PaymentReceiptFactory(status=PaymentReceiptStatusEnum.RECEIVED)
        payment = PaymentFactory(
            user=receipt.user,
            product=receipt.product,
            provider=receipt.provider,
            charge_id=receipt.charge_id,
        )

        applied = PaymentReceipt.objects.mark_applied(
            receipt_id=receipt.pk,
            lease_id=uuid.uuid4(),
            payment=payment,
        )

        self.assertFalse(applied)

    def test_applied_transition_persists_immutable_transition_timestamp(self) -> None:
        lease_id = uuid.uuid4()
        applied_at = timezone.now() - timedelta(minutes=5)
        receipt = PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.PROCESSING,
            lease_id=lease_id,
            processing_started_at=applied_at - timedelta(seconds=1),
        )
        payment = PaymentFactory(
            user=receipt.user,
            product=receipt.product,
            provider=receipt.provider,
            charge_id=receipt.charge_id,
        )

        applied = PaymentReceipt.objects.mark_applied(
            receipt_id=receipt.pk,
            lease_id=lease_id,
            payment=payment,
            applied_at=applied_at,
        )
        PaymentReceipt.objects.filter(pk=receipt.pk)._safe_update(
            updated_at=applied_at + timedelta(hours=1)
        )
        receipt.refresh_from_db()

        self.assertTrue(applied)
        self.assertEqual(receipt.applied_at, applied_at)

    def test_processing_requires_lease_and_timestamp_in_full_clean(self) -> None:
        receipt = PaymentReceiptFactory()
        receipt.status = PaymentReceiptStatusEnum.PROCESSING

        with self.assertRaises(ValidationError):
            receipt.full_clean()

    def test_processing_requires_lease_and_timestamp_in_database(self) -> None:
        with self.assertRaises(IntegrityError):
            PaymentReceiptFactory(status=PaymentReceiptStatusEnum.PROCESSING)

    def test_claim_is_atomic_and_sets_coherent_lease(self) -> None:
        receipt = PaymentReceiptFactory(status=PaymentReceiptStatusEnum.RECEIVED)
        lease_id = uuid.uuid4()
        started_at = timezone.now()

        claimed = PaymentReceipt.objects.claim_for_processing(
            receipt_id=receipt.pk,
            lease_id=lease_id,
            started_at=started_at,
        )
        duplicate_claim = PaymentReceipt.objects.claim_for_processing(
            receipt_id=receipt.pk,
            lease_id=uuid.uuid4(),
            started_at=started_at,
        )

        receipt.refresh_from_db()
        self.assertTrue(claimed)
        self.assertFalse(duplicate_claim)
        self.assertEqual(receipt.status, PaymentReceiptStatusEnum.PROCESSING)
        self.assertEqual(receipt.lease_id, lease_id)
        self.assertEqual(receipt.processing_started_at, started_at)
        self.assertEqual(receipt.attempt_count, 1)

    def test_retry_requires_exact_current_lease(self) -> None:
        receipt = PaymentReceiptFactory()
        lease_id = uuid.uuid4()
        started_at = timezone.now()
        PaymentReceipt.objects.claim_for_processing(
            receipt_id=receipt.pk,
            lease_id=lease_id,
            started_at=started_at,
        )

        wrong_lease = PaymentReceipt.objects.mark_for_retry(
            receipt_id=receipt.pk,
            lease_id=uuid.uuid4(),
            next_attempt_at=started_at + timedelta(minutes=1),
            error_code="temporary",
        )
        current_lease = PaymentReceipt.objects.mark_for_retry(
            receipt_id=receipt.pk,
            lease_id=lease_id,
            next_attempt_at=started_at + timedelta(minutes=1),
            error_code="temporary",
        )

        receipt.refresh_from_db()
        self.assertFalse(wrong_lease)
        self.assertTrue(current_lease)
        self.assertEqual(receipt.status, PaymentReceiptStatusEnum.RETRY)
        self.assertIsNone(receipt.lease_id)
        self.assertIsNone(receipt.processing_started_at)

    def test_received_recovery_conditionally_enters_due_retry(self) -> None:
        receipt = PaymentReceiptFactory(status=PaymentReceiptStatusEnum.RECEIVED)
        next_attempt_at = timezone.now()

        prepared = PaymentReceipt.objects.mark_received_for_retry(
            receipt_id=receipt.pk,
            next_attempt_at=next_attempt_at,
        )
        duplicate = PaymentReceipt.objects.mark_received_for_retry(
            receipt_id=receipt.pk,
            next_attempt_at=next_attempt_at + timedelta(minutes=1),
        )

        receipt.refresh_from_db()
        self.assertTrue(prepared)
        self.assertFalse(duplicate)
        self.assertEqual(receipt.status, PaymentReceiptStatusEnum.RETRY)
        self.assertEqual(receipt.attempt_count, 0)
        self.assertEqual(receipt.next_attempt_at, next_attempt_at)
        self.assertEqual(receipt.last_error_code, "enqueue_recovery")

    def test_crashed_claim_is_recovered_only_after_lease_becomes_stale(self) -> None:
        receipt = PaymentReceiptFactory()
        lease_id = uuid.uuid4()
        started_at = timezone.now()
        PaymentReceipt.objects.claim_for_processing(
            receipt_id=receipt.pk,
            lease_id=lease_id,
            started_at=started_at,
        )

        fresh = PaymentReceipt.objects.recover_stale_lease(
            receipt_id=receipt.pk,
            stale_before=started_at - timedelta(seconds=1),
            next_attempt_at=started_at + timedelta(minutes=1),
        )
        stale = PaymentReceipt.objects.recover_stale_lease(
            receipt_id=receipt.pk,
            stale_before=started_at,
            next_attempt_at=started_at + timedelta(minutes=1),
        )

        receipt.refresh_from_db()
        self.assertFalse(fresh)
        self.assertTrue(stale)
        self.assertEqual(receipt.status, PaymentReceiptStatusEnum.RETRY)
        self.assertIsNone(receipt.lease_id)

    def test_applied_completion_requires_exact_current_lease(self) -> None:
        receipt = PaymentReceiptFactory()
        payment = PaymentFactory(
            user=receipt.user,
            product=receipt.product,
            provider=receipt.provider,
            charge_id=receipt.charge_id,
        )
        lease_id = uuid.uuid4()
        PaymentReceipt.objects.claim_for_processing(
            receipt_id=receipt.pk,
            lease_id=lease_id,
            started_at=timezone.now(),
        )

        wrong_lease = PaymentReceipt.objects.mark_applied(
            receipt_id=receipt.pk,
            lease_id=uuid.uuid4(),
            payment=payment,
        )
        current_lease = PaymentReceipt.objects.mark_applied(
            receipt_id=receipt.pk,
            lease_id=lease_id,
            payment=payment,
        )

        receipt.refresh_from_db()
        self.assertFalse(wrong_lease)
        self.assertTrue(current_lease)
        self.assertEqual(receipt.status, PaymentReceiptStatusEnum.APPLIED)
        self.assertEqual(receipt.payment, payment)
        self.assertIsNone(receipt.lease_id)

    def test_legacy_payment_with_mismatched_owner_cannot_be_associated(self) -> None:
        receipt = PaymentReceiptFactory()
        payment = PaymentFactory(
            product=receipt.product,
            provider=receipt.provider,
            charge_id=receipt.charge_id,
        )
        lease_id = uuid.uuid4()
        PaymentReceipt.objects.claim_for_processing(
            receipt_id=receipt.pk,
            lease_id=lease_id,
            started_at=timezone.now(),
        )

        applied = PaymentReceipt.objects.mark_applied(
            receipt_id=receipt.pk,
            lease_id=lease_id,
            payment=payment,
        )

        receipt.refresh_from_db()
        self.assertFalse(applied)
        self.assertEqual(receipt.status, PaymentReceiptStatusEnum.PROCESSING)
        self.assertIsNone(receipt.payment)

    def test_processing_state_detects_stale_lease(self) -> None:
        receipt = PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.PROCESSING,
            processing_started_at=timezone.now() - timedelta(minutes=6),
            lease_id=uuid.uuid4(),
        )

        self.assertTrue(
            receipt.has_stale_lease(stale_before=timezone.now() - timedelta(minutes=5))
        )

    def test_applied_payment_relation_is_nullable_then_unique(self) -> None:
        receipt = PaymentReceiptFactory(payment=None)
        payment = PaymentFactory(
            user=receipt.user,
            product=receipt.product,
            provider=receipt.provider,
            charge_id=receipt.charge_id,
        )

        self.assertIsNone(receipt.payment)
        lease_id = uuid.uuid4()
        PaymentReceipt.objects.claim_for_processing(
            receipt_id=receipt.pk,
            lease_id=lease_id,
            started_at=timezone.now(),
        )
        PaymentReceipt.objects.mark_applied(
            receipt_id=receipt.pk,
            lease_id=lease_id,
            payment=payment,
        )

        with self.assertRaises(IntegrityError):
            PaymentReceiptFactory(
                payment=payment,
                status=PaymentReceiptStatusEnum.APPLIED,
            )
