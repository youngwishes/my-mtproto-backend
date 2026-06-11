from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class MyServerOut(BaseServiceDTO):
    """Один сервер в списке для пользователя."""

    location: str
    proxy_link: str


@dataclass(kw_only=True, frozen=True, slots=True)
class MyServersOut(BaseServiceDTO):
    """Ответ GetMyServersService: дата истечения + список серверов."""

    expired_date: str
    servers: list[MyServerOut]
