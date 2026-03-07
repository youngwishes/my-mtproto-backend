import json
from copy import copy
from dataclasses import asdict, dataclass

import httpx
from aiogram.types import LabeledPrice
from services.handle_error import log_service_error

import config
from config import API_URL


@dataclass(kw_only=True, slots=True, frozen=True)
class Response:
    title: str
    description: str
    currency: str
    provider_data: str
    send_email_to_provider: bool
    need_email: bool
    prices: list
    provider_token: str

    def asdict(self) -> dict:
        return asdict(self)


@dataclass(kw_only=True, slots=True, frozen=True)
class GetInvoiceDataService:
    url: str = API_URL + "/api/v1/payments/"

    @log_service_error
    async def __call__(self) -> Response:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.url,
                headers={"Bot-Auth-Token": config.BOT_AUTH_TOKEN},
            )
            response.raise_for_status()
            data = copy(response.json())
            prices = [
                LabeledPrice(
                    label=data.get("title"),
                    amount=data.pop("price"),
                )
            ]
            provider_data = json.dumps(data.pop("provider_data"))
            return Response(
                **data,
                provider_data=provider_data,
                prices=prices,
                provider_token=config.PROVIDER_TOKEN,
            )
