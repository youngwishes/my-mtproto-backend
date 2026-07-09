from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, final

from aiogram.types import LabeledPrice

if TYPE_CHECKING:
    from src.core.backend_client import BackendClient

_PRODUCT_PATH = "/api/v1/payments/"
_BUY_PATH = "/api/v1/payments/buy/"
_GIFT_BUY_PATH = "/api/v1/payments/gift-certificates/buy/"
_GIFT_ACTIVATE_PATH = "/api/v1/payments/gift-certificates/activate/"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CardInvoice:
    title: str
    description: str
    currency: str
    provider_data: str
    send_email_to_provider: bool
    need_email: bool
    prices: list[LabeledPrice]
    provider_token: str

    def asdict(self) -> dict[str, Any]:
        return asdict(self)


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class StarsInvoice:
    title: str
    description: str
    prices: list[LabeledPrice]
    currency: str = "XTR"
    provider_token: str = ""


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class GiftCertificate:
    code: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ActivatedGiftCertificate:
    expired_date: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class PaymentsClient:
    backend: BackendClient
    provider_token: str

    async def get_card_invoice(self) -> CardInvoice:
        data = await self.backend.get(_PRODUCT_PATH)
        return CardInvoice(
            title=data["title"],
            description=data["description"],
            currency=data["currency"],
            provider_data=json.dumps(data["provider_data"]),
            send_email_to_provider=data["send_email_to_provider"],
            need_email=data["need_email"],
            prices=[LabeledPrice(label=data["title"], amount=data["price"])],
            provider_token=self.provider_token,
        )

    async def get_stars_invoice(self) -> StarsInvoice:
        data = await self.backend.get(_PRODUCT_PATH)
        return StarsInvoice(
            title=data["title"],
            description=data["description"],
            prices=[LabeledPrice(label=data["title"], amount=data["stars_price"])],
        )

    async def confirm_purchase(
        self, *, telegram_id: str | int, charge_id: str, provider: str
    ) -> None:
        await self.backend.post(
            _BUY_PATH,
            data={
                "username": str(telegram_id),
                "charge_id": charge_id,
                "provider": provider,
            },
            telegram_id=telegram_id,
            expect_json=False,
        )

    async def confirm_gift_certificate_purchase(
        self, *, telegram_id: str | int, charge_id: str, provider: str
    ) -> GiftCertificate:
        response = await self.backend.post(
            _GIFT_BUY_PATH,
            data={
                "username": str(telegram_id),
                "charge_id": charge_id,
                "provider": provider,
            },
            telegram_id=telegram_id,
        )
        return GiftCertificate(**response)

    async def activate_gift_certificate(
        self, *, telegram_id: str | int, code: str
    ) -> ActivatedGiftCertificate:
        response = await self.backend.post(
            _GIFT_ACTIVATE_PATH,
            data={"username": str(telegram_id), "code": code},
            telegram_id=telegram_id,
        )
        return ActivatedGiftCertificate(**response)
