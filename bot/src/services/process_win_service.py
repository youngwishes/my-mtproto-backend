from dataclasses import asdict, dataclass

import httpx
from services.handle_error import log_service_error

import config


@dataclass(kw_only=True, slots=True, frozen=True)
class Response:
    link: str

    def asdict(self) -> dict:
        return asdict(self)


@dataclass(kw_only=True, slots=True, frozen=True)
class CheckAgreementWinService:
    url: str = config.API_URL + "/api/v1/users/check-agreement/"

    @log_service_error
    async def __call__(self, *, is_agree: bool, username: str) -> Response:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.url,
                json={"is_agree": is_agree, "username": str(username)},
                headers={"Bot-Auth-Token": config.BOT_AUTH_TOKEN},
            )
            response.raise_for_status()
            return Response(**response.json())
