from __future__ import annotations

from dataclasses import dataclass
import httpx
import config
from config import API_URL
from exceptions import APIError
from services.handle_error import log_service_error


@dataclass(kw_only=True, slots=True, frozen=True)
class BuyProductService:
    url: str = API_URL + "/api/v1/payments/buy/"

    @log_service_error
    async def __call__(
        self, *, telegram_id: int, charge_id: str, provider: str
    ) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.url,
                data={
                    "username": str(telegram_id),
                    "charge_id": charge_id,
                    "provider": provider,
                },
                headers={"Bot-Auth-Token": config.BOT_AUTH_TOKEN},
            )
            response.raise_for_status()
