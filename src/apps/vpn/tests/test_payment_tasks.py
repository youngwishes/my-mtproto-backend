from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import Mock, call, patch

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
        enqueue = Mock()
        service = RecoverPaymentReceiptsService(
            get_recoverable_receipts=lambda **_: [received, retry, stale],
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
        service.report_lease_recovery.assert_called_once_with()
        self.assertEqual(
            enqueue.call_args_list,
            [
                call(receipt_id=received.pk, countdown=2.5),
                call(receipt_id=retry.pk, countdown=2.5),
                call(receipt_id=stale.pk, countdown=2.5),
            ],
        )

    def test_lost_enqueue_remains_recoverable_and_does_not_skip_later_receipts(
        self,
    ) -> None:
        receipts = [PaymentReceiptFactory(), PaymentReceiptFactory()]
        enqueue = Mock(side_effect=[ConnectionError("broker down"), None])
        service = RecoverPaymentReceiptsService(
            get_recoverable_receipts=lambda **_: receipts,
            recover_stale_lease=Mock(),
            enqueue_receipt=enqueue,
            now=timezone.now,
            jitter_seconds=lambda: 0.0,
            stale_after=timedelta(minutes=5),
            batch_size=100,
        )

        self.assertEqual(service(), 1)

        receipts[0].refresh_from_db()
        self.assertEqual(receipts[0].status, PaymentReceiptStatusEnum.RECEIVED)
        self.assertEqual(enqueue.call_count, 2)

    def test_selector_is_bounded_and_receives_stale_cutoff(self) -> None:
        now = timezone.now()
        queryset = Mock()
        queryset.__getitem__ = Mock(return_value=[])
        selector = Mock(return_value=queryset)
        service = RecoverPaymentReceiptsService(
            get_recoverable_receipts=selector,
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

    @patch("apps.vpn.tasks.payment_receipts.get_recover_payment_receipts_service")
    def test_recovery_task_is_thin_vpn_owned_entrypoint(
        self, get_service: Mock
    ) -> None:
        get_service.return_value.return_value = 4
        from apps.vpn.tasks.payment_receipts import recover_payment_receipts_task

        self.assertEqual(recover_payment_receipts_task.run(), 4)
        get_service.return_value.assert_called_once_with()
