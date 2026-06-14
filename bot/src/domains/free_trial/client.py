from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from src.core.backend_client import BackendClient

_CHECK_PATH = "/api/v1/users/check-first-free-link/"
_CLAIM_PATH = "/api/v1/users/first-free-link/"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FreeTrialKey:
    expired_date: str
    link: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FreeTrialClient:
    backend: BackendClient

    async def check_availability(
        self,
        *,
        telegram_id: str,
        telegram_username: str,
        invited_from_username: str | None = None,
    ) -> str | None:
        data = {"username": telegram_id, "telegram_username": telegram_username}
        if invited_from_username is not None:
            data["invited_from_username"] = invited_from_username
        response = await self.backend.post(
            _CHECK_PATH, data=data, telegram_id=telegram_id
        )
        return response.get("available_free_period")

    async def claim(self, *, telegram_id: str) -> FreeTrialKey:
        response = await self.backend.post(
            _CLAIM_PATH, data={"username": telegram_id}, telegram_id=telegram_id
        )
        return FreeTrialKey(**response)
