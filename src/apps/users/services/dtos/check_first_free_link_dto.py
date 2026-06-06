from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class CheckFirstFreeLinkIn(BaseServiceDTO):
    """Входные данные для проверки доступности бесплатного периода."""

    username: str
    telegram_username: str
    invited_from_username: str | None = None
