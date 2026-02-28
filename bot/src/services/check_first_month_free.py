from dataclasses import dataclass

import httpx

import config
from config import API_URL
from exceptions import APIError
from services.handle_error import log_service_error


@dataclass(kw_only=True, slots=True, frozen=True)
class CheckFirstMonthFreeService:
    url: str = API_URL + "/api/v1/users/check-first-month-free/"

    @log_service_error
    async def __call__(self, *, telegram_id: str) -> str:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url,
                    data={"username": telegram_id},
                    headers={"Bot-Auth-Token": config.BOT_AUTH_TOKEN},
                )
                response.raise_for_status()
                return response.json().get("has_access_for_free")
        except Exception as exc:
            raise APIError(
                telegram_id=telegram_id,
                request_url=self.url,
                error=str(exc),
            )
