from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, final
from uuid import UUID

from django.utils import timezone

from apps.payments.enums import PlategaPaymentIntentStatusEnum
from apps.payments.selectors import (
    cancel_platega_intent,
    get_platega_intent_by_provider_transaction_id,
)
from apps.payments.services.dtos import (
    PlategaCallbackDTO,
    PlategaCallbackWarningDTO,
    ValidatedPlategaPaymentDTO,
    ValidatePlategaCallbackOut,
)


_CONFIRMED_STATES = (
    PlategaPaymentIntentStatusEnum.ACTIVE,
    PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED,
    PlategaPaymentIntentStatusEnum.RETRYABLE,
    PlategaPaymentIntentStatusEnum.PROCESSING,
    PlategaPaymentIntentStatusEnum.FULFILLED,
)


def _warning(
    *,
    reason_code: str,
    intent_id: int | None,
    provider_transaction_id: UUID | None,
) -> ValidatePlategaCallbackOut:
    return ValidatePlategaCallbackOut(
        payment=None,
        reason_code=reason_code,
        warning=PlategaCallbackWarningDTO(
            reason_code=reason_code,
            intent_id=intent_id,
            provider_transaction_id=provider_transaction_id,
        ),
    )


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ValidatePlategaCallbackService:
    """Match an authenticated callback to stored Platega intent fields."""

    clock: Callable[[], datetime]

    def __call__(
        self,
        *,
        callback: PlategaCallbackDTO,
    ) -> ValidatePlategaCallbackOut:
        intent = get_platega_intent_by_provider_transaction_id(
            provider_transaction_id=callback.transaction_id,
        )
        if intent is None:
            return _warning(
                reason_code="unknown_transaction",
                intent_id=None,
                provider_transaction_id=callback.transaction_id,
            )

        if callback.status not in {"CONFIRMED", "CANCELED"}:
            return _warning(
                reason_code="unsupported_status",
                intent_id=intent.pk,
                provider_transaction_id=intent.provider_transaction_id,
            )

        if (
            callback.transaction_id != intent.provider_transaction_id
            or callback.amount < intent.rub_amount
            or callback.currency != intent.currency
            or callback.payment_method != intent.payment_method
        ):
            return _warning(
                reason_code="callback_mismatch",
                intent_id=intent.pk,
                provider_transaction_id=intent.provider_transaction_id,
            )

        if callback.status == "CANCELED":
            canceled = cancel_platega_intent(
                intent_id=intent.pk,
                canceled_at=self.clock(),
            )
            return ValidatePlategaCallbackOut(
                payment=None,
                reason_code="canceled" if canceled == 1 else "duplicate",
                warning=None,
            )

        if intent.status not in _CONFIRMED_STATES:
            return ValidatePlategaCallbackOut(
                payment=None,
                reason_code="duplicate",
                warning=None,
            )

        return ValidatePlategaCallbackOut(
            payment=ValidatedPlategaPaymentDTO(
                intent_id=intent.pk,
                transaction_id=callback.transaction_id,
            ),
            reason_code="confirmed",
            warning=None,
        )


def get_validate_platega_callback_service() -> ValidatePlategaCallbackService:
    return ValidatePlategaCallbackService(clock=timezone.now)
