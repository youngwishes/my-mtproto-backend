from __future__ import annotations

from dataclasses import dataclass

import httpx
from aiogram.types import LabeledPrice
from services.handle_error import log_service_error

import config
from config import API_URL


@dataclass(kw_only=True, slots=True, frozen=True)
class StarsInvoiceResponse:
    title: str
    description: str
    prices: list
    currency: str = "XTR"
    provider_token: str = ""


@dataclass(kw_only=True, slots=True, frozen=True)
class GetStarsInvoiceDataService:
    url: str = API_URL + "/api/v1/payments/"

    @log_service_error
    async def __call__(self) -> StarsInvoiceResponse:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.url,
                headers={"Bot-Auth-Token": config.BOT_AUTH_TOKEN},
            )
            response.raise_for_status()
            data = response.json()
            prices = [
                LabeledPrice(
                    label=data["title"],
                    amount=data["stars_price"],
                )
            ]
            return StarsInvoiceResponse(
                title=data["title"],
                description=data["description"],
                prices=prices,
            )
