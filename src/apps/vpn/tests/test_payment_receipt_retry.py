from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch as MockPatch

from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import PaymentReceiptStatusEnum
from apps.payments.exceptions import PaymentReceiptDatabaseBusy
from apps.payments.models import Payment
from apps.payments.services.apply_payment_receipt import get_apply_payment_receipt_service
from apps.payments.services.dtos import VPNPaymentFulfillmentIn
from apps.payments.tests.factories import PaymentReceiptFactory
from apps.vpn.models import VPNAccess, VPNPurchase
from apps.vpn.services.fulfill_purchase import get_fulfill_purchase_service
from apps.vpn.services.retry_payment_receipt import (
    RetryPaymentReceiptService,
    get_retry_payment_receipt_service,
)


class RetryPaymentReceiptServiceTest(TestCase):
    def setUp(self) -> None:
        self.now = timezone.now()
        self.receipt = PaymentReceiptFactory()
        self.lease_id = uuid.uuid4()
        type(self.receipt).objects.claim_for_processing(
            receipt_id=self.receipt.pk,
            lease_id=self.lease_id,
            started_at=self.now,
        )

    def test_marks_exact_lease_for_retry_with_safe_bounded_backoff(self) -> None:
        service = RetryPaymentReceiptService(
            get_receipt=lambda **_: type(self.receipt).objects.get(pk=self.receipt.pk),
            mark_for_retry=type(self.receipt).objects.mark_for_retry,
            now=lambda: self.now,
            jitter_seconds=lambda: 3.0,
            base_delay_seconds=10,
            max_delay_seconds=60,
        )

        changed = service(
            receipt_id=self.receipt.pk,
            lease_id=self.lease_id,
            error=RuntimeError("provider-secret-must-not-be-stored"),
        )

        self.assertTrue(changed)
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, PaymentReceiptStatusEnum.RETRY)
        self.assertEqual(self.receipt.attempt_count, 1)
        self.assertEqual(self.receipt.next_attempt_at, self.now + timedelta(seconds=13))
        self.assertEqual(self.receipt.last_error_code, "unexpected_apply_error")
        self.assertNotIn("provider-secret", self.receipt.last_error_code)

    def test_repeated_attempt_uses_incremented_attempt_count_and_caps_delay(self) -> None:
        type(self.receipt).objects.mark_for_retry(
            receipt_id=self.receipt.pk,
            lease_id=self.lease_id,
            next_attempt_at=self.now,
            error_code="database_busy",
        )
        second_lease = uuid.uuid4()
        type(self.receipt).objects.claim_for_processing(
            receipt_id=self.receipt.pk,
            lease_id=second_lease,
            started_at=self.now,
        )
        service = RetryPaymentReceiptService(
            get_receipt=lambda **_: type(self.receipt).objects.get(pk=self.receipt.pk),
            mark_for_retry=type(self.receipt).objects.mark_for_retry,
            now=lambda: self.now,
            jitter_seconds=lambda: 20.0,
            base_delay_seconds=25,
            max_delay_seconds=60,
        )

        service(
            receipt_id=self.receipt.pk,
            lease_id=second_lease,
            error=PaymentReceiptDatabaseBusy(self.receipt.pk),
        )

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.attempt_count, 2)
        self.assertEqual(self.receipt.next_attempt_at, self.now + timedelta(seconds=60))
        self.assertEqual(self.receipt.last_error_code, "database_busy")

    def test_lease_race_cannot_overwrite_newer_owner(self) -> None:
        newer_lease = uuid.uuid4()
        type(self.receipt).objects.filter(pk=self.receipt.pk)._safe_update(
            lease_id=newer_lease
        )
        mark_for_retry = Mock(wraps=type(self.receipt).objects.mark_for_retry)
        service = RetryPaymentReceiptService(
            get_receipt=lambda **_: type(self.receipt).objects.get(pk=self.receipt.pk),
            mark_for_retry=mark_for_retry,
            now=lambda: self.now,
            jitter_seconds=lambda: 0.0,
            base_delay_seconds=10,
            max_delay_seconds=60,
        )

        self.assertFalse(
            service(
                receipt_id=self.receipt.pk,
                lease_id=self.lease_id,
                error=RuntimeError("secret"),
            )
        )

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, PaymentReceiptStatusEnum.PROCESSING)
        self.assertEqual(self.receipt.lease_id, newer_lease)
        mark_for_retry.assert_not_called()

    def test_failed_task_audits_retry_then_successful_retry_applies_once(self) -> None:
        receipt = PaymentReceiptFactory()
        lease_id = uuid.uuid4()

        def fail_after_vpn_write(*, purchase: VPNPaymentFulfillmentIn) -> None:
            VPNAccess.objects.create(
                user_id=purchase.user_id,
                expired_at=purchase.accepted_at + timedelta(days=30),
            )
            raise RuntimeError("provider-secret-must-not-leak")

        apply_service = get_apply_payment_receipt_service(
            fulfill_purchase=fail_after_vpn_write,
            now=lambda: self.now,
            sleep=lambda _: None,
        )
        retry_service = RetryPaymentReceiptService(
            get_receipt=lambda **_: type(receipt).objects.get(pk=receipt.pk),
            mark_for_retry=type(receipt).objects.mark_for_retry,
            now=lambda: self.now,
            jitter_seconds=lambda: 0.0,
            base_delay_seconds=10,
            max_delay_seconds=60,
        )
        lock_context = Mock()
        lock_context.__enter__ = Mock(return_value=True)
        lock_context.__exit__ = Mock(return_value=None)
        from apps.vpn.tasks.payment_receipts import apply_payment_receipt_task

        with (
            self.assertRaisesRegex(RuntimeError, "vpn payment receipt apply failed"),
            self.settings(VPN_PAYMENT_RETRY_BASE_SECONDS=10),
            MockPatch(
                "apps.vpn.tasks.payment_receipts.get_payment_writer_lock",
                return_value=Mock(return_value=lock_context),
            ),
            MockPatch(
                "apps.vpn.tasks.payment_receipts.get_vpn_payment_receipt_service",
                return_value=apply_service,
            ),
            MockPatch(
                "apps.vpn.tasks.payment_receipts.get_retry_payment_receipt_service",
                return_value=retry_service,
            ),
            MockPatch(
                "apps.vpn.tasks.payment_receipts.uuid.uuid4",
                return_value=lease_id,
            ),
        ):
            apply_payment_receipt_task.run(receipt_id=receipt.pk)

        receipt.refresh_from_db()
        self.assertEqual(receipt.status, PaymentReceiptStatusEnum.RETRY)
        self.assertEqual(receipt.attempt_count, 1)
        self.assertEqual(receipt.last_error_code, "unexpected_apply_error")
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(VPNAccess.objects.exists())
        self.assertFalse(VPNPurchase.objects.exists())

        successful_service = get_apply_payment_receipt_service(
            fulfill_purchase=get_fulfill_purchase_service(
                register_after_commit_callback=lambda _: None,
            ),
            now=lambda: self.now + timedelta(seconds=11),
            sleep=lambda _: None,
        )
        successful_service(receipt_id=receipt.pk, lease_id=uuid.uuid4())
        replay = successful_service(receipt_id=receipt.pk, lease_id=uuid.uuid4())

        receipt.refresh_from_db()
        self.assertEqual(receipt.status, PaymentReceiptStatusEnum.APPLIED)
        self.assertEqual(receipt.attempt_count, 2)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(VPNAccess.objects.count(), 1)
        self.assertEqual(VPNPurchase.objects.count(), 1)
        self.assertTrue(replay.is_replay)

    def test_factory_rejects_invalid_delay_settings(self) -> None:
        invalid_settings = (
            (0, 60, 1.0),
            (-1, 60, 1.0),
            (60, 59, 1.0),
            (1, 86_401, 1.0),
            (1, 60, -1.0),
            (1, 60, float("nan")),
            (1, 60, float("inf")),
            (1, 60, 301.0),
        )

        for base, maximum, jitter in invalid_settings:
            with self.subTest(base=base, maximum=maximum, jitter=jitter):
                with self.assertRaises(ValueError):
                    get_retry_payment_receipt_service(
                        base_delay_seconds=base,
                        max_delay_seconds=maximum,
                        jitter_max_seconds=jitter,
                    )

    def test_factory_preserves_valid_delay_settings(self) -> None:
        service = get_retry_payment_receipt_service(
            base_delay_seconds=10,
            max_delay_seconds=60,
            jitter_max_seconds=0,
        )

        self.assertEqual(service.base_delay_seconds, 10)
        self.assertEqual(service.max_delay_seconds, 60)
        self.assertEqual(service.jitter_seconds(), 0.0)
