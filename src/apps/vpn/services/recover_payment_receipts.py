from __future__ import annotations

import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import final

from django.utils import timezone

from apps.payments.enums import PaymentReceiptStatusEnum
from apps.payments.models import PaymentReceipt
from apps.payments.selectors import get_recoverable_payment_receipts


def _bounded_jitter_seconds() -> float:
    return random.uniform(0.0, 5.0)


def _report_lease_recovery() -> None:
    from apps.vpn.observability import VPNMetric, emit_vpn_metric

    try:
        emit_vpn_metric(VPNMetric(name="vpn_receipt_lease_recovery_total", value=1))
    except Exception:
        pass


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class RecoverPaymentReceiptsService:
    """Recover durable receipts without making broker delivery authoritative."""

    get_recoverable_receipts: Callable[..., Iterable[PaymentReceipt]]
    recover_stale_lease: Callable[..., bool]
    enqueue_receipt: Callable[..., None]
    now: Callable[[], datetime]
    jitter_seconds: Callable[[], float]
    stale_after: timedelta
    batch_size: int
    report_lease_recovery: Callable[[], None] = _report_lease_recovery

    def __call__(self) -> int:
        current_time = self.now()
        receipts = self.get_recoverable_receipts(
            due_at=current_time,
            stale_before=current_time - self.stale_after,
        )
        bounded_receipts = list(receipts[: self.batch_size])
        enqueued = 0
        for receipt in bounded_receipts:
            if receipt.status == PaymentReceiptStatusEnum.PROCESSING:
                recovered = self.recover_stale_lease(
                    receipt_id=receipt.pk,
                    stale_before=current_time - self.stale_after,
                    next_attempt_at=current_time,
                )
                if not recovered:
                    continue
                try:
                    self.report_lease_recovery()
                except Exception:
                    pass
            try:
                self.enqueue_receipt(
                    receipt_id=receipt.pk,
                    countdown=self.jitter_seconds(),
                )
            except Exception:
                # The unchanged receipt is selected again by the next Beat pass.
                continue
            enqueued += 1
        return enqueued


def get_recover_payment_receipts_service(
    *,
    enqueue_receipt: Callable[..., None],
    now: Callable[[], datetime] = timezone.now,
) -> RecoverPaymentReceiptsService:
    return RecoverPaymentReceiptsService(
        get_recoverable_receipts=get_recoverable_payment_receipts,
        recover_stale_lease=PaymentReceipt.objects.recover_stale_lease,
        enqueue_receipt=enqueue_receipt,
        now=now,
        jitter_seconds=_bounded_jitter_seconds,
        stale_after=timedelta(minutes=5),
        batch_size=100,
    )
