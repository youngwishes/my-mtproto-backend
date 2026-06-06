from __future__ import annotations

from apps.users.models import SystemUser


def get_user_by_username(*, username: str) -> SystemUser | None:
    """Находит пользователя по Telegram ID (хранится в поле username)."""
    return SystemUser.objects.filter(username=username).first()


def get_free_used_count() -> int:
    """Количество пользователей, использовавших бесплатный период."""
    return SystemUser.objects.filter(first_month_free_used=True).count()


def get_total_referrals_count(*, username: str) -> int:
    """Общее количество приглашённых пользователей."""
    return SystemUser.objects.filter(invited_from_username=username).count()


def get_active_referrals_count(*, username: str) -> int:
    """Количество приглашённых пользователей, активировавших реферал."""
    return SystemUser.objects.filter(
        invited_from_username=username,
        referral_activated=True,
    ).count()
