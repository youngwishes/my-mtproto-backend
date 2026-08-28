from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable, Protocol, final

from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.payments.apple_cashback import APPLES_PER_DAY, get_apple_level
from apps.payments.enums import AppleRedemptionModeEnum
from apps.payments.exceptions import (
    AppleKeyRequired,
    AppleRedemptionRetryable,
    InsufficientApples,
    InvalidAppleRedemption,
    StaleAppleRedemption,
)
from apps.payments.selectors.common import (
    get_payment_user_for_update,
)
from apps.payments.selectors.apples import (
    count_apple_cashback_purchases,
    create_apple_redemption,
    get_apple_redemption_for_update,
    get_existing_apple_redemption_key,
    get_existing_apple_redemption_key_for_update,
)
from apps.payments.services.dtos import (
    AppleRedemptionConfirmIn,
    AppleRedemptionConfirmOut,
    AppleRedemptionPreviewIn,
    AppleRedemptionPreviewOut,
    AppleStatusIn,
    AppleStatusOut,
)
from apps.users.selectors import get_user_by_username

if TYPE_CHECKING:
    from apps.payments.models import AppleRedemption


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class GetAppleStatusService:
    """Return the user's current fixed-rule apple loyalty status."""

    clock: Callable[[], datetime]

    def __call__(self, *, request: AppleStatusIn) -> AppleStatusOut:
        try:
            return self._get_status(request=request)
        except DatabaseError as exc:
            raise AppleRedemptionRetryable(telegram_id=request.username) from exc

    def _get_status(self, *, request: AppleStatusIn) -> AppleStatusOut:
        user = get_user_by_username(username=request.username)
        if user is None:
            raise InvalidAppleRedemption(telegram_id=request.username)

        purchase_count = count_apple_cashback_purchases(user_id=user.pk)
        level = get_apple_level(eligible_purchase_count=purchase_count)
        next_count = level.next_level_purchase_count
        return AppleStatusOut(
            balance=user.apple_balance,
            eligible_purchase_count=purchase_count,
            level=level.name,
            rate_percent=level.rate_percent,
            next_level_purchase_count=next_count,
            purchases_to_next_level=(
                None if next_count is None else next_count - purchase_count
            ),
            is_max_level=next_count is None,
            redeemable_days=user.apple_balance // APPLES_PER_DAY,
            missing_apples=max(APPLES_PER_DAY - user.apple_balance, 0),
            has_existing_key=get_existing_apple_redemption_key(
                user_id=user.pk,
                now=self.clock(),
            )
            is not None,
        )


def get_apple_status_service() -> GetAppleStatusService:
    return GetAppleStatusService(clock=timezone.now)


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class PreviewAppleRedemptionService:
    """Save a display-stable apple quote without spending or extending."""

    clock: Callable[[], datetime]

    def __call__(
        self, *, request: AppleRedemptionPreviewIn
    ) -> AppleRedemptionPreviewOut:
        try:
            return self._preview(request=request)
        except DatabaseError as exc:
            raise AppleRedemptionRetryable(telegram_id=request.username) from exc

    def _preview(
        self, *, request: AppleRedemptionPreviewIn
    ) -> AppleRedemptionPreviewOut:
        user = get_user_by_username(username=request.username)
        if user is None:
            raise InvalidAppleRedemption(telegram_id=request.username)
        try:
            mode = AppleRedemptionModeEnum(request.mode)
        except ValueError as exc:
            raise InvalidAppleRedemption(telegram_id=request.username) from exc
        if user.apple_balance < APPLES_PER_DAY:
            raise InsufficientApples(
                request.username,
                missing_apples=APPLES_PER_DAY - user.apple_balance,
            )
        preview_at = self.clock()
        key = get_existing_apple_redemption_key(
            user_id=user.pk,
            now=preview_at,
        )
        if key is None or key.expired_date is None:
            raise AppleKeyRequired(telegram_id=request.username)

        apples_spent = (
            APPLES_PER_DAY
            if mode is AppleRedemptionModeEnum.ONE_DAY
            else (user.apple_balance // APPLES_PER_DAY) * APPLES_PER_DAY
        )
        days = apples_spent // APPLES_PER_DAY
        projected_expiry = max(key.expired_date, preview_at) + timedelta(days=days)
        redemption = create_apple_redemption(
            user_id=user.pk,
            key_id=key.pk,
            apples_spent=apples_spent,
            quoted_expired_at=projected_expiry,
        )
        return AppleRedemptionPreviewOut(
            confirmation_id=redemption.pk,
            mode=mode.value,
            apples_spent=apples_spent,
            days=days,
            projected_expired_date=projected_expiry.date().strftime("%d.%m.%y"),
        )


def get_preview_apple_redemption_service() -> PreviewAppleRedemptionService:
    return PreviewAppleRedemptionService(clock=timezone.now)


class EnqueueAppleKeyPush(Protocol):
    def __call__(self, *, key_id: int) -> None: ...


def _confirmed_redemption_outcome(
    *, redemption: AppleRedemption
) -> AppleRedemptionConfirmOut:
    assert redemption.new_expired_at is not None
    assert redemption.balance_after is not None
    return AppleRedemptionConfirmOut(
        apples_spent=redemption.apples_spent,
        days=redemption.apples_spent // APPLES_PER_DAY,
        expired_date=redemption.new_expired_at.date().strftime("%d.%m.%y"),
        balance=redemption.balance_after,
    )


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ConfirmAppleRedemptionService:
    """Atomically spend a saved quote and extend its selected existing key."""

    clock: Callable[[], datetime]
    enqueue_push: EnqueueAppleKeyPush

    def __call__(
        self, *, request: AppleRedemptionConfirmIn
    ) -> AppleRedemptionConfirmOut:
        try:
            with transaction.atomic():
                redemption = get_apple_redemption_for_update(
                    confirmation_id=request.confirmation_id
                )
                if redemption is None or redemption.user.username != request.username:
                    raise InvalidAppleRedemption(telegram_id=request.username)
                if redemption.new_expired_at is not None:
                    return _confirmed_redemption_outcome(redemption=redemption)

                user = get_payment_user_for_update(username=request.username)
                if user is None:
                    raise InvalidAppleRedemption(telegram_id=request.username)
                confirmation_at = self.clock()
                key = get_existing_apple_redemption_key_for_update(
                    user_id=user.pk,
                    now=confirmation_at,
                )
                if (
                    redemption.key_id is None
                    or key is None
                    or key.pk != redemption.key_id
                    or key.expired_date is None
                    or user.apple_balance < redemption.apples_spent
                ):
                    raise StaleAppleRedemption(telegram_id=request.username)

                days = redemption.apples_spent // APPLES_PER_DAY
                new_expiry = max(key.expired_date, confirmation_at) + timedelta(
                    days=days
                )
                reactivated = (
                    not key.is_active
                    or key.was_deleted
                    or key.expired_date <= confirmation_at
                )
                balance_after = user.apple_balance - redemption.apples_spent

                user.apple_balance = balance_after
                user.save(update_fields=["apple_balance"])
                key.expired_date = new_expiry
                key.user_notified = False
                key.is_active = True
                key.was_deleted = False
                key.save(
                    update_fields=[
                        "expired_date",
                        "user_notified",
                        "is_active",
                        "was_deleted",
                    ]
                )
                redemption.new_expired_at = new_expiry
                redemption.balance_after = balance_after
                redemption.save(update_fields=["new_expired_at", "balance_after"])

                if reactivated:
                    transaction.on_commit(
                        lambda key_id=key.pk: self.enqueue_push(key_id=key_id)
                    )
                return _confirmed_redemption_outcome(redemption=redemption)
        except DatabaseError as exc:
            raise AppleRedemptionRetryable(telegram_id=request.username) from exc


def _enqueue_apple_key_push(*, key_id: int) -> None:
    from apps.vds.tasks import push_key_to_servers_task

    push_key_to_servers_task.delay(key_id=key_id)


def get_confirm_apple_redemption_service() -> ConfirmAppleRedemptionService:
    return ConfirmAppleRedemptionService(
        clock=timezone.now,
        enqueue_push=_enqueue_apple_key_push,
    )
