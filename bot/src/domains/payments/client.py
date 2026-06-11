from __future__ import annotations

import json
from copy import copy
from dataclasses import asdict, dataclass, field
from typing import final

from aiogram.types import LabeledPrice

from core import config
from core.backend_client import BackendClient
from core.handle_error import log_service_error


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class InvoiceData:
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


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class StarsInvoiceData:
    title: str
    description: str
    prices: list
    currency: str = "XTR"
    provider_token: str = ""


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class PaymentsClient:
    _http: BackendClient = field(default_factory=BackendClient)

    async def get_invoice_data(self) -> InvoiceData:
        raw = copy(await self._http.get(path="/api/v1/payments/"))
        prices = [LabeledPrice(label=raw.get("title"), amount=raw.pop("price"))]
        provider_data = json.dumps(raw.pop("provider_data"))
        raw.pop("stars_price", None)
        return InvoiceData(
            **raw,
            provider_data=provider_data,
            prices=prices,
            provider_token=config.PROVIDER_TOKEN,
        )

    async def get_stars_invoice_data(self) -> StarsInvoiceData:
        raw = await self._http.get(path="/api/v1/payments/")
        prices = [LabeledPrice(label=raw["title"], amount=raw["stars_price"])]
        return StarsInvoiceData(
            title=raw["title"],
            description=raw["description"],
            prices=prices,
        )

    @log_service_error
    async def record_purchase(
        self, *, telegram_id: int, charge_id: str, provider: str
    ) -> None:
        await self._http.post(
            path="/api/v1/payments/buy/",
            telegram_id=str(telegram_id),
            data={
                "username": str(telegram_id),
                "charge_id": charge_id,
                "provider": provider,
            },
        )


def get_payments_client() -> PaymentsClient:
    return PaymentsClient()
