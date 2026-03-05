from dataclasses import dataclass

import httpx
from exceptions import APIError
from services.handle_error import log_service_error

import config
from config import API_URL


@dataclass(kw_only=True, slots=True, frozen=True)
class CheckFirstMonthFreeService:
    url: str = API_URL + "/api/v1/users/check-first-month-free/"

    @log_service_error
    async def __call__(self, *, telegram_id: str, telegram_username: str) -> str:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url,
                    data={
                        "username": telegram_id,
                        "telegram_username": telegram_username,
                    },
                    headers={"Bot-Auth-Token": config.BOT_AUTH_TOKEN},
                )
                response.raise_for_status()
                return response.json().get("available_free_period")
        except Exception as exc:
            raise APIError(
                telegram_id=telegram_id,
                request_url=self.url,
                error=str(exc),
            )
