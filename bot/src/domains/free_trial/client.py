from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from src.exceptions import APIError

if TYPE_CHECKING:
    from src.core.backend_client import BackendClient

_CHECK_PATH = "/api/v1/users/check-first-free-link/"
_CLAIM_PATH = "/api/v1/users/first-free-link/"
_CONSENT_STATUS_PATH = "/api/v1/users/consent/status/"
_CONSENT_ACCEPT_PATH = "/api/v1/users/consent/accept/"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FreeTrialKey:
    expired_date: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FreeTrialClient:
    backend: BackendClient

    @staticmethod
    def _consent_value(*, response: object, telegram_id: str) -> bool:
        value = (
            response.get("legal_terms_accepted")
            if isinstance(response, dict)
            else None
        )
        if type(value) is not bool:
            raise APIError(
                telegram_id,
                error="Invalid legal consent response.",
            )
        return value

    async def get_consent_status(self, *, telegram_id: str) -> bool:
        response = await self.backend.post(
            _CONSENT_STATUS_PATH,
            data={"username": telegram_id},
            telegram_id=telegram_id,
        )
        return self._consent_value(response=response, telegram_id=telegram_id)

    async def accept_consent(
        self,
        *,
        telegram_id: str,
        telegram_username: str | None,
        invited_from_username: str | None = None,
    ) -> bool:
        data = {"username": telegram_id}
        if telegram_username is not None:
            data["telegram_username"] = telegram_username
        if invited_from_username is not None:
            data["invited_from_username"] = invited_from_username
        response = await self.backend.post(
            _CONSENT_ACCEPT_PATH,
            data=data,
            telegram_id=telegram_id,
        )
        accepted = self._consent_value(
            response=response,
            telegram_id=telegram_id,
        )
        if accepted is not True:
            raise APIError(
                telegram_id,
                error="Legal consent was not saved.",
            )
        return accepted

    async def check_availability(
        self,
        *,
        telegram_id: str,
        telegram_username: str | None,
        invited_from_username: str | None = None,
    ) -> str | None:
        data = {"username": telegram_id}
        if telegram_username is not None:
            data["telegram_username"] = telegram_username
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
