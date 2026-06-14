from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from src.core.backend_client import BackendClient

_SERVERS_PATH = "/api/v1/users/my-servers/"
_UPDATE_PATH = "/api/v1/users/update-link/"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ServerItem:
    location: str
    proxy_link: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class MyServers:
    expired_date: str
    servers: list[ServerItem]


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReissuedKey:
    expired_date: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class LinksClient:
    backend: BackendClient

    async def get_my_servers(self, *, telegram_id: str) -> MyServers:
        response = await self.backend.post(
            _SERVERS_PATH, data={"username": telegram_id}, telegram_id=telegram_id
        )
        return MyServers(
            expired_date=response["expired_date"],
            servers=[ServerItem(**item) for item in response["servers"]],
        )

    async def reissue(self, *, telegram_id: str) -> ReissuedKey:
        response = await self.backend.post(
            _UPDATE_PATH, data={"username": telegram_id}, telegram_id=telegram_id
        )
        return ReissuedKey(**response)
