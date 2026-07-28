from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from src.exceptions import APIError

if TYPE_CHECKING:
    from src.core.backend_client import BackendClient

_STATUS_PATH = "/api/v1/users/consent/status/"
_ACCEPT_PATH = "/api/v1/users/consent/accept/"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ConsentStatus:
    legal_terms_accepted: bool


def _parse_consent_status(
    response: object,
    *,
    telegram_id: str,
    request_path: str,
    require_accepted: bool,
) -> ConsentStatus:
    if isinstance(response, dict):
        accepted = response.get("legal_terms_accepted")
    else:
        accepted = None
    if type(accepted) is not bool or (require_accepted and accepted is not True):
        raise APIError(
            telegram_id,
            request_url=request_path,
            error="Invalid legal consent response.",
        )
    return ConsentStatus(legal_terms_accepted=accepted)


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ConsentClient:
    backend: BackendClient

    async def get_status(self, *, telegram_id: str) -> ConsentStatus:
        response = await self.backend.post(
            _STATUS_PATH,
            data={"username": telegram_id},
            telegram_id=telegram_id,
        )
        return _parse_consent_status(
            response,
            telegram_id=telegram_id,
            request_path=_STATUS_PATH,
            require_accepted=False,
        )

    async def accept(
        self,
        *,
        telegram_id: str,
        telegram_username: str | None,
        invited_from_username: str | None = None,
    ) -> ConsentStatus:
        data = {"username": telegram_id}
        if telegram_username is not None:
            data["telegram_username"] = telegram_username
        if invited_from_username is not None:
            data["invited_from_username"] = invited_from_username
        response = await self.backend.post(
            _ACCEPT_PATH,
            data=data,
            telegram_id=telegram_id,
        )
        return _parse_consent_status(
            response,
            telegram_id=telegram_id,
            request_path=_ACCEPT_PATH,
            require_accepted=True,
        )
