from dataclasses import dataclass
import json
import httpx

import config
from config import API_URL
from exceptions import APIError
from services.handle_error import log_service_error


@dataclass(kw_only=True, slots=True, frozen=True)
class FirstMonthFreeService:
    url: str = API_URL + "/api/v1/users/first-month-free/"

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
                return response.json().get("link")
        except Exception as exc:
            try:
                body = json.loads(exc.response.content)
            except Exception:
                raise APIError(
                    telegram_id=telegram_id,
                    request_url=self.url,
                    error=str(exc),
                )
            else:
                raise APIError(
                    telegram_id=telegram_id,
                    request_url=self.url,
                    error=str(exc),
                    message=body.get("error"),
                )

