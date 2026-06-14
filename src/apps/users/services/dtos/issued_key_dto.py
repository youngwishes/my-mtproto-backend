from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class IssuedKeyOut(BaseServiceDTO):
    """Результат выдачи ключа: дата окончания.

    Ссылки на серверы не возвращаются — ключ валиден на всём флоте,
    бот показывает кнопку «📡 Мои серверы».
    """

    expired_date: str
