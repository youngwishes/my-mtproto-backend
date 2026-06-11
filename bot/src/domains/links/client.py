from __future__ import annotations

from dataclasses import dataclass, field
from typing import final

from core.backend_client import BackendClient
from core.handle_error import log_service_error


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class UpdatedLink:
    link: str
    expired_date: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class LinksClient:
    _http: BackendClient = field(default_factory=BackendClient)

    @log_service_error
    async def update(self, *, telegram_id: str) -> UpdatedLink:
        result = await self._http.post(
            path="/api/v1/users/update-link/",
            telegram_id=telegram_id,
            data={"username": telegram_id},
        )
        return UpdatedLink(link=result["link"], expired_date=result["expired_date"])


def get_links_client() -> LinksClient:
    return LinksClient()
