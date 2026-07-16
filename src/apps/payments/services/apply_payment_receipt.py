from __future__ import annotations

import random
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, final
from uuid import UUID

from django.db import OperationalError, transaction
from django.utils import timezone

from apps.payments.enums import PaymentKindEnum, PaymentReceiptStatusEnum
from apps.payments.exceptions import (
    PaymentReceiptDatabaseBusy,
    PaymentReceiptLeaseUnavailable,
    PaymentReceiptNotFound,
    PaymentReceiptTransactionBoundaryViolation,
)
from apps.payments.models import Payment, PaymentReceipt
from apps.payments.selectors import get_payment_receipt_by_id
from apps.payments.services.dtos import (
    AppliedPaymentReceiptOut,
    VPNPaymentFulfillmentIn,
)

if TYPE_CHECKING:
    from apps.payments.services.contracts import VPNPaymentFulfillment


def _lock_retry_delay(attempt: int) -> float:
    """Return a short jittered delay for bounded SQLite lock retries."""
    return random.uniform(0.01, 0.05) * attempt


_SQLITE_CONTENTION_ERROR_NAMES = frozenset(
    {
        "SQLITE_BUSY",
        "SQLITE_BUSY_RECOVERY",
        "SQLITE_BUSY_SNAPSHOT",
        "SQLITE_BUSY_TIMEOUT",
        "SQLITE_LOCKED",
        "SQLITE_LOCKED_SHAREDCACHE",
        "SQLITE_LOCKED_VTAB",
    }
)
_SQLITE_CONTENTION_MESSAGES = (
    "database is locked",
    "database table is locked",
    "database schema is locked",
    "database is busy",
)


def _is_sqlite_lock_contention(exc: OperationalError) -> bool:
    """Recognize only SQLite lock/busy failures safe for whole-transaction retry."""
    candidates = (exc, exc.__cause__)
    for candidate in candidates:
        if candidate is None:
            continue
        errorcode = getattr(candidate, "sqlite_errorcode", None)
        if isinstance(errorcode, int):
            return errorcode & 0xFF in {
                sqlite3.SQLITE_BUSY,
                sqlite3.SQLITE_LOCKED,
            }
        errorname = getattr(candidate, "sqlite_errorname", None)
        if isinstance(errorname, str):
            return errorname in _SQLITE_CONTENTION_ERROR_NAMES

    for candidate in candidates:
        if candidate is None:
            continue
        message = " ".join(str(candidate).casefold().split())
        if any(
            message == canonical or message.startswith(f"{canonical}:")
            for canonical in _SQLITE_CONTENTION_MESSAGES
        ):
            return True
        representation = message.partition(":")[0].upper()
        if representation in _SQLITE_CONTENTION_ERROR_NAMES:
            return True
    return False


def _ensure_durable_transaction_boundary(*, receipt_id: int) -> None:
    """Reject a caller transaction before the receipt or its domain is mutated."""
    try:
        with transaction.atomic(durable=True):
            pass
    except RuntimeError:
        raise PaymentReceiptTransactionBoundaryViolation(receipt_id) from None


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ApplyPaymentReceiptService:
    """Durably claim then atomically apply one task-owned receipt lease."""

    get_receipt: Callable[..., PaymentReceipt | None]
    claim_receipt: Callable[..., bool]
    create_payment: Callable[..., Payment]
    fulfill_purchase: VPNPaymentFulfillment
    mark_applied: Callable[..., bool]
    now: Callable[[], datetime]
    sleep: Callable[[float], None]
    lock_retry_delay: Callable[[int], float]
    ensure_transaction_boundary: Callable[..., None]
    max_lock_attempts: int = 3

    def __call__(
        self,
        *,
        receipt_id: int,
        lease_id: UUID,
    ) -> AppliedPaymentReceiptOut:
        self.ensure_transaction_boundary(receipt_id=receipt_id)
        receipt = self.get_receipt(receipt_id=receipt_id)
        if receipt is None:
            raise PaymentReceiptNotFound(receipt_id)
        if receipt.status == PaymentReceiptStatusEnum.APPLIED:
            return self._replay(receipt=receipt)

        self._claim(receipt_id=receipt_id, lease_id=lease_id)
        return self._fulfill_with_lock_retry(
            receipt_id=receipt_id,
            lease_id=lease_id,
        )

    def _claim(self, *, receipt_id: int, lease_id: UUID) -> None:
        started_at = self.now()
        for attempt in range(1, self.max_lock_attempts + 1):
            try:
                with transaction.atomic(durable=True):
                    claimed = self.claim_receipt(
                        receipt_id=receipt_id,
                        lease_id=lease_id,
                        started_at=started_at,
                    )
                    if claimed:
                        return
                    current = self.get_receipt(receipt_id=receipt_id)
                    if (
                        current is not None
                        and current.status == PaymentReceiptStatusEnum.APPLIED
                    ):
                        return
                    raise PaymentReceiptLeaseUnavailable(receipt_id)
            except OperationalError as exc:
                self._handle_lock_error(
                    exc=exc,
                    receipt_id=receipt_id,
                    attempt=attempt,
                )
        raise AssertionError("unreachable")

    def _fulfill_with_lock_retry(
        self,
        *,
        receipt_id: int,
        lease_id: UUID,
    ) -> AppliedPaymentReceiptOut:
        for attempt in range(1, self.max_lock_attempts + 1):
            try:
                with transaction.atomic():
                    receipt = self.get_receipt(receipt_id=receipt_id)
                    if receipt is None:
                        raise PaymentReceiptNotFound(receipt_id)
                    if receipt.status == PaymentReceiptStatusEnum.APPLIED:
                        return self._replay(receipt=receipt)
                    if (
                        receipt.status != PaymentReceiptStatusEnum.PROCESSING
                        or receipt.lease_id != lease_id
                    ):
                        raise PaymentReceiptLeaseUnavailable(receipt_id)
                    payment = self.create_payment(
                        user=receipt.user,
                        key=None,
                        product=receipt.product,
                        provider=receipt.provider,
                        charge_id=receipt.charge_id,
                        kind=PaymentKindEnum.SUBSCRIPTION,
                    )
                    fulfilled = self.fulfill_purchase(
                        purchase=VPNPaymentFulfillmentIn(
                            receipt_id=receipt.pk,
                            payment_id=payment.pk,
                            user_id=receipt.user_id,
                            accepted_at=receipt.accepted_at,
                        )
                    )
                    applied_at = self.now()
                    if not self.mark_applied(
                        receipt_id=receipt.pk,
                        lease_id=lease_id,
                        payment=payment,
                        applied_at=applied_at,
                        ready_at=applied_at if fulfilled.is_ready else None,
                    ):
                        raise PaymentReceiptLeaseUnavailable(receipt_id)
                    return AppliedPaymentReceiptOut(
                        receipt_id=receipt.pk,
                        payment_id=payment.pk,
                        access_id=fulfilled.access_id,
                        purchase_id=fulfilled.purchase_id,
                        is_replay=False,
                    )
            except OperationalError as exc:
                self._handle_lock_error(
                    exc=exc,
                    receipt_id=receipt_id,
                    attempt=attempt,
                )
        raise AssertionError("unreachable")

    def _handle_lock_error(
        self,
        *,
        exc: OperationalError,
        receipt_id: int,
        attempt: int,
    ) -> None:
        if not _is_sqlite_lock_contention(exc):
            raise exc
        if attempt == self.max_lock_attempts:
            raise PaymentReceiptDatabaseBusy(receipt_id) from exc
        self.sleep(self.lock_retry_delay(attempt))

    def _replay(self, *, receipt: PaymentReceipt) -> AppliedPaymentReceiptOut:
        if receipt.payment_id is None:
            raise PaymentReceiptLeaseUnavailable(receipt.pk)
        return AppliedPaymentReceiptOut(
            receipt_id=receipt.pk,
            payment_id=receipt.payment_id,
            access_id=None,
            purchase_id=None,
            is_replay=True,
        )


def get_apply_payment_receipt_service(
    *,
    fulfill_purchase: VPNPaymentFulfillment,
    now: Callable[[], datetime] = timezone.now,
    sleep: Callable[[float], None] = time.sleep,
) -> ApplyPaymentReceiptService:
    """Wire payment-owned persistence only to the injected fulfillment contract."""
    return ApplyPaymentReceiptService(
        get_receipt=get_payment_receipt_by_id,
        claim_receipt=PaymentReceipt.objects.claim_for_processing,
        create_payment=Payment.objects.create,
        fulfill_purchase=fulfill_purchase,
        mark_applied=PaymentReceipt.objects.mark_applied,
        now=now,
        sleep=sleep,
        lock_retry_delay=_lock_retry_delay,
        ensure_transaction_boundary=_ensure_durable_transaction_boundary,
    )
