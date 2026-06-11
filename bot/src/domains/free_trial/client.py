from __future__ import annotations

from dataclasses import dataclass, field
from typing import final

from core.backend_client import BackendClient
from core.handle_error import log_service_error
from domains.free_trial.enums import FreeAvailable


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FreeLink:
    link: str
    expired_date: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FreeTrialClient:
    _http: BackendClient = field(default_factory=BackendClient)

    @log_service_error
    async def check_eligibility(
        self,
        *,
        telegram_id: str,
        telegram_username: str | None,
        invited_from_username: str | None = None,
    ) -> FreeAvailable:
        data: dict = {"username": telegram_id, "telegram_username": telegram_username}
        if invited_from_username is not None:
            data["invited_from_username"] = invited_from_username
        result = await self._http.post(
            path="/api/v1/users/check-first-free-link/",
            telegram_id=telegram_id,
            data=data,
        )
        return FreeAvailable(result["available_free_period"])

    @log_service_error
    async def activate(self, *, telegram_id: str) -> FreeLink:
        result = await self._http.post(
            path="/api/v1/users/first-free-link/",
            telegram_id=telegram_id,
            data={"username": telegram_id},
        )
        return FreeLink(link=result["link"], expired_date=result["expired_date"])


def get_free_trial_client() -> FreeTrialClient:
    return FreeTrialClient()
