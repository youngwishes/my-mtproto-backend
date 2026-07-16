from __future__ import annotations

import uuid
import traceback
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.payments.enums import PaymentReceiptStatusEnum
from apps.payments.tests.factories import PaymentReceiptFactory
from apps.vpn.services.recover_payment_receipts import RecoverPaymentReceiptsService


class RecoverPaymentReceiptsServiceTest(TestCase):
    def test_enqueues_received_due_retry_and_recovered_stale_lease_with_bounded_jitter(
        self,
    ) -> None:
        now = timezone.now()
        received = PaymentReceiptFactory(status=PaymentReceiptStatusEnum.RECEIVED)
        retry = PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.RETRY,
            next_attempt_at=now,
        )
        stale = PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.PROCESSING,
            processing_started_at=now - timedelta(minutes=6),
            lease_id=uuid.uuid4(),
        )
        enqueued_statuses: list[str] = []

        def enqueue(*, receipt_id: int, countdown: float) -> None:
            del countdown
            enqueued_statuses.append(
                type(received).objects.get(pk=receipt_id).status
            )

        service = RecoverPaymentReceiptsService(
            get_recoverable_receipts=lambda **_: [received, retry, stale],
            prepare_received_retry=type(received).objects.mark_received_for_retry,
            recover_stale_lease=type(stale).objects.recover_stale_lease,
            enqueue_receipt=enqueue,
            now=lambda: now,
            jitter_seconds=lambda: 2.5,
            stale_after=timedelta(minutes=5),
            batch_size=100,
            report_lease_recovery=Mock(),
        )

        result = service()

        stale.refresh_from_db()
        self.assertEqual(stale.status, PaymentReceiptStatusEnum.RETRY)
        self.assertEqual(stale.last_error_code, "stale_lease")
        self.assertEqual(stale.next_attempt_at, now)
        self.assertEqual(result, 3)
        self.assertEqual(
            enqueued_statuses,
            [
                PaymentReceiptStatusEnum.RETRY,
                PaymentReceiptStatusEnum.RETRY,
                PaymentReceiptStatusEnum.RETRY,
            ],
        )
        service.report_lease_recovery.assert_called_once_with()

    def test_lost_enqueue_remains_recoverable_and_does_not_skip_later_receipts(
        self,
    ) -> None:
        receipts = [PaymentReceiptFactory(), PaymentReceiptFactory()]
        enqueue = Mock(side_effect=[ConnectionError("broker down"), None])
        service = RecoverPaymentReceiptsService(
            get_recoverable_receipts=lambda **_: receipts,
            prepare_received_retry=type(receipts[0]).objects.mark_received_for_retry,
            recover_stale_lease=Mock(),
            enqueue_receipt=enqueue,
            now=timezone.now,
            jitter_seconds=lambda: 0.0,
            stale_after=timedelta(minutes=5),
            batch_size=100,
        )

        self.assertEqual(service(), 1)

        receipts[0].refresh_from_db()
        self.assertEqual(receipts[0].status, PaymentReceiptStatusEnum.RETRY)
        self.assertEqual(receipts[0].last_error_code, "enqueue_recovery")
        self.assertEqual(enqueue.call_count, 2)

    def test_selector_is_bounded_and_receives_stale_cutoff(self) -> None:
        now = timezone.now()
        queryset = Mock()
        queryset.__getitem__ = Mock(return_value=[])
        selector = Mock(return_value=queryset)
        service = RecoverPaymentReceiptsService(
            get_recoverable_receipts=selector,
            prepare_received_retry=Mock(),
            recover_stale_lease=Mock(),
            enqueue_receipt=Mock(),
            now=lambda: now,
            jitter_seconds=lambda: 0.0,
            stale_after=timedelta(minutes=5),
            batch_size=17,
        )

        service()

        selector.assert_called_once_with(
            due_at=now,
            stale_before=now - timedelta(minutes=5),
        )
        queryset.__getitem__.assert_called_once_with(slice(None, 17, None))


class PaymentReceiptTaskTest(SimpleTestCase):
    @patch("apps.vpn.tasks.payment_receipts.get_payment_writer_lock")
    @patch("apps.vpn.tasks.payment_receipts.get_vpn_payment_receipt_service")
    @patch("apps.vpn.tasks.payment_receipts.get_retry_payment_receipt_service")
    def test_invalid_retry_settings_fail_before_lock_and_receipt_claim(
        self,
        get_retry_service: Mock,
        get_apply_service: Mock,
        get_lock: Mock,
    ) -> None:
        get_retry_service.side_effect = ValueError("invalid retry settings")
        from apps.vpn.tasks.payment_receipts import apply_payment_receipt_task

        with self.assertRaisesRegex(ValueError, "invalid retry settings"):
            apply_payment_receipt_task.run(receipt_id=41)

        get_lock.assert_not_called()
        get_apply_service.assert_not_called()

    @patch("apps.vpn.tasks.payment_receipts.get_payment_writer_lock")
    @patch("apps.vpn.tasks.payment_receipts.get_vpn_payment_receipt_service")
    def test_apply_task_holds_lock_while_calling_vpn_composition_root(
        self,
        get_service: Mock,
        get_lock: Mock,
    ) -> None:
        events: list[str] = []
        lock_context = Mock()
        lock_context.__enter__ = Mock(side_effect=lambda: events.append("lock") or True)
        lock_context.__exit__ = Mock(side_effect=lambda *_: events.append("unlock"))
        get_lock.return_value.return_value = lock_context
        get_service.return_value.side_effect = lambda **_: events.append("apply")
        from apps.vpn.tasks.payment_receipts import apply_payment_receipt_task

        apply_payment_receipt_task.run(receipt_id=41)

        self.assertEqual(events, ["lock", "apply", "unlock"])
        kwargs = get_service.return_value.call_args.kwargs
        self.assertEqual(kwargs["receipt_id"], 41)
        self.assertIsInstance(kwargs["lease_id"], uuid.UUID)

    @patch("apps.vpn.tasks.payment_receipts.get_retry_payment_receipt_service")
    @patch("apps.vpn.tasks.payment_receipts.get_payment_writer_lock")
    @patch("apps.vpn.tasks.payment_receipts.get_vpn_payment_receipt_service")
    def test_apply_task_never_exposes_unexpected_exception_text(
        self,
        get_service: Mock,
        get_lock: Mock,
        get_retry_service: Mock,
    ) -> None:
        lock_context = Mock()
        lock_context.__enter__ = Mock(return_value=True)
        lock_context.__exit__ = Mock(return_value=None)
        get_lock.return_value.return_value = lock_context
        get_service.return_value.side_effect = RuntimeError(
            "provider-secret-that-must-not-be-logged"
        )
        from apps.vpn.tasks.payment_receipts import apply_payment_receipt_task

        lease_id = uuid.uuid4()
        with (
            patch("apps.vpn.tasks.payment_receipts.uuid.uuid4", return_value=lease_id),
            self.assertRaises(RuntimeError) as raised,
        ):
            apply_payment_receipt_task.run(receipt_id=41)

        self.assertNotIn("provider-secret", str(raised.exception))
        self.assertEqual(str(raised.exception), "vpn payment receipt apply failed")
        rendered_traceback = "".join(
            traceback.format_exception(raised.exception)
        )
        self.assertNotIn("provider-secret", rendered_traceback)
        get_retry_service.return_value.assert_called_once()
        retry_kwargs = get_retry_service.return_value.call_args.kwargs
        self.assertEqual(retry_kwargs["receipt_id"], 41)
        self.assertEqual(retry_kwargs["lease_id"], lease_id)
        self.assertIs(retry_kwargs["error"], get_service.return_value.side_effect)

    @patch("apps.vpn.tasks.payment_receipts.get_recover_payment_receipts_service")
    def test_recovery_task_is_thin_vpn_owned_entrypoint(
        self, get_service: Mock
    ) -> None:
        get_service.return_value.return_value = 4
        from apps.vpn.tasks.payment_receipts import recover_payment_receipts_task

        self.assertEqual(recover_payment_receipts_task.run(), 4)
        get_service.return_value.assert_called_once_with()
