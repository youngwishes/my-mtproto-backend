from __future__ import annotations

from apps.users.models import SystemUser


def get_user_by_username(*, username: str) -> SystemUser | None:
    """Находит пользователя по Telegram ID (хранится в поле username)."""
    return SystemUser.objects.filter(username=username).first()
