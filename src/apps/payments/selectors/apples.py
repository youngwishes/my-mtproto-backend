from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from django.db.models import QuerySet

from apps.payments.models import (
    AppleCashbackPurchase,
    AppleRedemption,
)
from apps.vds.models import MTPRotoKey

if TYPE_CHECKING:
    pass


def get_apple_cashback_purchase_by_identity(
    *, identity_key: str
) -> AppleCashbackPurchase | None:
    """Return the saved eligible-purchase outcome for a provider identity."""
    return (
        AppleCashbackPurchase.objects.select_related("payment", "payment__user")
        .filter(identity_key=identity_key)
        .first()
    )


def count_apple_cashback_purchases(*, user_id: int) -> int:
    """Count completed eligible purchases, including launch history."""
    return AppleCashbackPurchase.objects.filter(payment__user_id=user_id).count()


def get_existing_apple_redemption_key(
    *, user_id: int, now: datetime
) -> MTPRotoKey | None:
    """Select the user's best valid key, then their best existing dated key."""
    return _select_existing_apple_redemption_key(
        keys=MTPRotoKey.objects.filter(user_id=user_id),
        now=now,
    )


def get_existing_apple_redemption_key_for_update(
    *, user_id: int, now: datetime
) -> MTPRotoKey | None:
    """Lock and select the user's key eligible for confirmed redemption."""
    return _select_existing_apple_redemption_key(
        keys=MTPRotoKey.objects.select_for_update().filter(user_id=user_id),
        now=now,
    )


def _select_existing_apple_redemption_key(
    *, keys: QuerySet[MTPRotoKey], now: datetime
) -> MTPRotoKey | None:
    active = (
        keys.active()
        .filter(was_deleted=False, expired_date__gt=now)
        .order_by("-expired_date", "-pk")
        .first()
    )
    if active is not None:
        return active
    return (
        keys.filter(expired_date__isnull=False).order_by("-expired_date", "-pk").first()
    )


def get_apple_redemption_for_update(*, confirmation_id: int) -> AppleRedemption | None:
    """Lock a saved quote/outcome and load its owner."""
    return (
        AppleRedemption.objects.select_for_update()
        .select_related("user")
        .filter(pk=confirmation_id)
        .first()
    )


def create_apple_redemption(
    *,
    user_id: int,
    key_id: int,
    apples_spent: int,
    quoted_expired_at: datetime,
) -> AppleRedemption:
    """Persist one immutable pending apple-redemption quote."""
    return AppleRedemption.objects.create(
        user_id=user_id,
        key_id=key_id,
        apples_spent=apples_spent,
        quoted_expired_at=quoted_expired_at,
    )


def create_apple_cashback_purchase(
    *,
    payment_id: int,
    identity_key: str,
    rate_percent: int,
    apples_earned: int,
    balance_after: int,
    eligible_purchase_count_after: int,
    result_expired_at: datetime | None,
) -> AppleCashbackPurchase:
    """Persist the immutable loyalty snapshot for one eligible payment."""
    return AppleCashbackPurchase.objects.create(
        payment_id=payment_id,
        identity_key=identity_key,
        rate_percent=rate_percent,
        apples_earned=apples_earned,
        balance_after=balance_after,
        eligible_purchase_count_after=eligible_purchase_count_after,
        result_expired_at=result_expired_at,
    )
