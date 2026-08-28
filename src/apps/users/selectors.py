from __future__ import annotations

from django.db.models import F, QuerySet

from apps.users.models import SystemUser


def get_user_by_username(*, username: str) -> SystemUser | None:
    """Находит пользователя по Telegram ID (хранится в поле username)."""
    return SystemUser.objects.filter(username=username).first()


def accept_legal_terms(
    *,
    username: str,
    telegram_username: str,
    invited_from_username: str | None,
) -> SystemUser:
    """Создаёт согласившегося пользователя или подтверждает существующего."""
    user, _ = SystemUser.objects.update_or_create(
        username=username,
        defaults={"legal_terms_accepted": True},
        create_defaults={
            "telegram_username": telegram_username,
            "invited_from_username": invited_from_username,
            "legal_terms_accepted": True,
        },
    )
    return user


def get_free_used_count() -> int:
    """Количество пользователей, использовавших бесплатный период."""
    return SystemUser.objects.filter(first_month_free_used=True).count()


def get_daily_free_trial_candidates() -> QuerySet[SystemUser]:
    """Пользователи, ожидающие бесплатный период, от старых к новым."""
    return SystemUser.objects.filter(first_month_free_used=False).order_by(
        "date_joined", "pk"
    )


def get_total_referrals_count(*, username: str) -> int:
    """Общее количество приглашённых пользователей."""
    return SystemUser.objects.filter(invited_from_username=username).count()


def get_active_referrals_count(*, username: str) -> int:
    """Количество приглашённых пользователей, активировавших реферал."""
    return SystemUser.objects.filter(
        invited_from_username=username,
        referral_activated=True,
    ).count()


def credit_user_apples(*, username: str, apples: int) -> None:
    """Атомарно начисляет яблоки пользователю."""
    SystemUser.objects.filter(username=username).update(
        apple_balance=F("apple_balance") + apples,
    )
