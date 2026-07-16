from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import final
from uuid import UUID

from django.utils import timezone

from apps.payments.enums import PaymentReceiptStatusEnum
from apps.payments.exceptions import (
    PaymentReceiptDatabaseBusy,
    PaymentReceiptLeaseUnavailable,
    PaymentReceiptNotFound,
)
from apps.payments.models import PaymentReceipt
from apps.payments.selectors import get_payment_receipt_by_id


MAX_RETRY_DELAY_SECONDS = 86_400
MAX_RETRY_JITTER_SECONDS = 300.0


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class RetryPaymentReceiptService:
    """Persist a bounded retry for the exact failed receipt lease."""

    get_receipt: Callable[..., PaymentReceipt | None]
    mark_for_retry: Callable[..., bool]
    now: Callable[[], datetime]
    jitter_seconds: Callable[[], float]
    base_delay_seconds: int
    max_delay_seconds: int

    def __call__(
        self,
        *,
        receipt_id: int,
        lease_id: UUID,
        error: Exception,
    ) -> bool:
        receipt = self.get_receipt(receipt_id=receipt_id)
        if (
            receipt is None
            or receipt.status != PaymentReceiptStatusEnum.PROCESSING
            or receipt.lease_id != lease_id
        ):
            return False
        delay_seconds = self._retry_delay(attempt_count=receipt.attempt_count)
        return self.mark_for_retry(
            receipt_id=receipt_id,
            lease_id=lease_id,
            next_attempt_at=self.now() + timedelta(seconds=delay_seconds),
            error_code=self._error_code(error=error),
        )

    def _retry_delay(self, *, attempt_count: int) -> float:
        exponent = min(max(attempt_count - 1, 0), 30)
        exponential = self.base_delay_seconds * (2**exponent)
        jitter = max(self.jitter_seconds(), 0.0)
        return min(float(self.max_delay_seconds), exponential + jitter)

    def _error_code(self, *, error: Exception) -> str:
        if isinstance(error, PaymentReceiptDatabaseBusy):
            return "database_busy"
        if isinstance(error, PaymentReceiptLeaseUnavailable):
            return "lease_unavailable"
        if isinstance(error, PaymentReceiptNotFound):
            return "receipt_not_found"
        return "unexpected_apply_error"


def get_retry_payment_receipt_service(
    *,
    base_delay_seconds: int,
    max_delay_seconds: int,
    jitter_max_seconds: float,
    now: Callable[[], datetime] = timezone.now,
) -> RetryPaymentReceiptService:
    """Wire retry persistence with settings-owned delay bounds."""
    if (
        isinstance(base_delay_seconds, bool)
        or not isinstance(base_delay_seconds, int)
        or base_delay_seconds <= 0
    ):
        raise ValueError("VPN payment retry base must be a positive integer")
    if (
        isinstance(max_delay_seconds, bool)
        or not isinstance(max_delay_seconds, int)
        or max_delay_seconds < base_delay_seconds
        or max_delay_seconds > MAX_RETRY_DELAY_SECONDS
    ):
        raise ValueError("VPN payment retry max is outside the supported range")
    if (
        isinstance(jitter_max_seconds, bool)
        or not isinstance(jitter_max_seconds, (int, float))
        or not math.isfinite(jitter_max_seconds)
        or jitter_max_seconds < 0
        or jitter_max_seconds > MAX_RETRY_JITTER_SECONDS
    ):
        raise ValueError("VPN payment retry jitter is outside the supported range")
    return RetryPaymentReceiptService(
        get_receipt=get_payment_receipt_by_id,
        mark_for_retry=PaymentReceipt.objects.mark_for_retry,
        now=now,
        jitter_seconds=lambda: random.uniform(0.0, jitter_max_seconds),
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
    )
