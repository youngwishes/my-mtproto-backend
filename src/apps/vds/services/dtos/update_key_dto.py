from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class UpdateKeyOut(BaseServiceDTO):
    """Результат обновления ключа: ссылка и дата окончания."""

    link: str
    expired_date: str
