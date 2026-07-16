from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, final

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.payments.enums import PaymentIntentStatusEnum, ProductCodeEnum
from apps.payments.exceptions import (
    PaymentIdentityConflict,
    PaymentIntentMismatch,
    PaymentIntentNotFound,
)
from apps.payments.models import PaymentReceipt
from apps.payments.selectors import (
    get_payment_by_identity,
    get_payment_intent_by_payload,
    get_payment_receipt_by_identity,
    get_payment_receipt_by_intent_id,
)
from apps.payments.services.dtos import AcceptedPaymentReceiptOut, PaymentReceiptData

if TYPE_CHECKING:
    from apps.payments.models import Payment, PaymentIntent
    from apps.payments.services.dtos import AcceptPaymentReceiptIn


def register_after_commit(callback: Callable[[], None]) -> None:
    """Run an optional acceleration callback without weakening durable recovery."""
    transaction.on_commit(callback, robust=True)


def _noop_schedule_receipt(*, receipt_id: int) -> None:
    """Leave the durable RECEIVED row for periodic recovery until B-009 wiring."""


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class AcceptPaymentReceiptService:
    """Persist an exact approved Telegram payment before any fulfillment work."""

    get_intent: Callable[..., PaymentIntent | None]
    get_receipt: Callable[..., PaymentReceipt | None]
    get_receipt_by_intent: Callable[..., PaymentReceipt | None]
    get_payment: Callable[..., Payment | None]
    create_receipt: Callable[..., PaymentReceipt]
    register_after_commit: Callable[[Callable[[], None]], None]
    schedule_receipt: Callable[..., None]

    def __call__(
        self,
        *,
        payment: AcceptPaymentReceiptIn,
    ) -> AcceptedPaymentReceiptOut:
        intent = self.get_intent(invoice_payload=payment.invoice_payload)
        if intent is None:
            raise PaymentIntentNotFound(payment.username)
        if not self._matches_intent(payment=payment, intent=intent):
            raise PaymentIntentMismatch(payment.username)

        existing = self.get_receipt(
            provider=payment.provider,
            charge_id=payment.charge_id,
        )
        if existing is not None:
            if not self._matches_receipt(
                payment=payment, intent=intent, receipt=existing
            ):
                raise PaymentIdentityConflict(payment.username)
            return self._result(receipt=existing, is_replay=True)

        if intent.status != PaymentIntentStatusEnum.APPROVED:
            raise PaymentIntentMismatch(payment.username)
        if self.get_payment(provider=payment.provider, charge_id=payment.charge_id):
            raise PaymentIdentityConflict(payment.username)

        try:
            with transaction.atomic():
                receipt = self.create_receipt(
                    intent=intent,
                    user=intent.user,
                    product=intent.product,
                    provider=payment.provider,
                    charge_id=payment.charge_id,
                    currency=payment.currency,
                    amount=payment.amount,
                )
                try:
                    intent.transition_to(status=PaymentIntentStatusEnum.PAID)
                except ValidationError as exc:
                    raise PaymentIntentMismatch(payment.username) from exc
                try:
                    self.register_after_commit(
                        partial(self.schedule_receipt, receipt_id=receipt.pk)
                    )
                except Exception:
                    # RECEIVED remains the durable recovery source if registration
                    # or an eagerly executed broker callback fails.
                    pass
        except IntegrityError:
            winner = self.get_receipt(
                provider=payment.provider,
                charge_id=payment.charge_id,
            )
            if winner is None:
                winner = self.get_receipt_by_intent(intent_id=intent.pk)
            if winner is None:
                raise PaymentIdentityConflict(payment.username) from None
            if not self._matches_receipt(
                payment=payment,
                intent=intent,
                receipt=winner,
            ):
                raise PaymentIdentityConflict(payment.username) from None
            return self._result(receipt=winner, is_replay=True)
        return self._result(receipt=receipt, is_replay=False)

    def _matches_intent(
        self,
        *,
        payment: AcceptPaymentReceiptIn,
        intent: PaymentIntent,
    ) -> bool:
        return (
            bool(payment.charge_id)
            and intent.user.username == payment.username
            and intent.product.code == ProductCodeEnum.VLESS_30D
            and intent.provider == payment.provider
            and intent.currency == payment.currency
            and intent.amount == payment.amount
        )

    def _matches_receipt(
        self,
        *,
        payment: AcceptPaymentReceiptIn,
        intent: PaymentIntent,
        receipt: PaymentReceipt,
    ) -> bool:
        return PaymentReceiptData(
            intent_id=intent.pk,
            user_id=intent.user_id,
            product_id=intent.product_id,
            provider=payment.provider,
            charge_id=payment.charge_id,
            currency=payment.currency,
            amount=payment.amount,
        ).matches(receipt=receipt)

    def _result(
        self,
        *,
        receipt: PaymentReceipt,
        is_replay: bool,
    ) -> AcceptedPaymentReceiptOut:
        return AcceptedPaymentReceiptOut(
            receipt_id=receipt.pk,
            status=receipt.status,
            is_replay=is_replay,
        )


def get_accept_payment_receipt_service(
    *,
    schedule_receipt: Callable[..., None] = _noop_schedule_receipt,
) -> AcceptPaymentReceiptService:
    return AcceptPaymentReceiptService(
        get_intent=get_payment_intent_by_payload,
        get_receipt=get_payment_receipt_by_identity,
        get_receipt_by_intent=get_payment_receipt_by_intent_id,
        get_payment=get_payment_by_identity,
        create_receipt=PaymentReceipt.objects.create,
        register_after_commit=register_after_commit,
        schedule_receipt=schedule_receipt,
    )
