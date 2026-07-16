from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, final

from aiogram.types import LabeledPrice

if TYPE_CHECKING:
    from src.core.backend_client import BackendClient

VPNCurrency = Literal["RUB", "XTR"]

_PAYMENT_INTENT_PATH = "/api/v1/vpn/payment-intents/"
_PRE_CHECKOUT_PATH = "/api/v1/vpn/pre-checkout/"
_PAYMENT_PATH = "/api/v1/vpn/payments/"
_STATUS_PATH = "/api/v1/vpn/status/"
_REISSUE_PATH = "/api/v1/vpn/reissue/"


class VPNAccessStatus(StrEnum):
    NOT_PURCHASED = "NOT_PURCHASED"
    PREPARING = "PREPARING"
    READY = "READY"
    EXPIRED = "EXPIRED"
    DISABLED = "DISABLED"


class VPNPaymentReceiptStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    APPLIED = "APPLIED"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNInvoice:
    title: str
    description: str
    invoice_payload: str
    currency: VPNCurrency
    provider: str
    prices: list[LabeledPrice]
    expires_at: str
    provider_token: str
    provider_data: str | None
    send_email_to_provider: bool
    need_email: bool

    def telegram_kwargs(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "title": self.title,
            "description": self.description,
            "payload": self.invoice_payload,
            "currency": self.currency,
            "prices": self.prices,
            "provider_token": self.provider_token,
        }
        if self.provider_data is not None:
            result.update(
                provider_data=self.provider_data,
                send_email_to_provider=self.send_email_to_provider,
                need_email=self.need_email,
            )
        return result


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNStatus:
    status: VPNAccessStatus
    expired_at: str | None = None
    subscription_url: str | None = None


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNClient:
    backend: BackendClient
    provider_token: str
    sales_enabled: bool

    async def create_invoice(
        self, *, telegram_id: str | int, currency: VPNCurrency
    ) -> VPNInvoice:
        data = await self.backend.post(
            _PAYMENT_INTENT_PATH,
            data={"username": str(telegram_id), "currency": currency},
            telegram_id=telegram_id,
        )
        amount_key = "stars_price" if currency == "XTR" else "price"
        return VPNInvoice(
            title=data["title"],
            description=data["description"],
            invoice_payload=data["invoice_payload"],
            currency=data["currency"],
            provider=data["provider"],
            prices=[LabeledPrice(label=data["title"], amount=data[amount_key])],
            expires_at=data["expires_at"],
            provider_token="" if currency == "XTR" else self.provider_token,
            provider_data=(
                json.dumps(data["provider_data"]) if currency == "RUB" else None
            ),
            send_email_to_provider=data.get("send_email_to_provider", False),
            need_email=data.get("need_email", False),
        )

    async def approve_pre_checkout(
        self,
        *,
        telegram_id: str | int,
        invoice_payload: str,
        currency: VPNCurrency,
        amount: int,
    ) -> None:
        await self.backend.post(
            _PRE_CHECKOUT_PATH,
            data={
                "username": str(telegram_id),
                "invoice_payload": invoice_payload,
                "currency": currency,
                "amount": amount,
            },
            telegram_id=telegram_id,
        )

    async def accept_payment(
        self,
        *,
        telegram_id: str | int,
        invoice_payload: str,
        provider: str,
        charge_id: str,
        currency: VPNCurrency,
        amount: int,
    ) -> VPNPaymentReceiptStatus:
        data = await self.backend.post(
            _PAYMENT_PATH,
            data={
                "username": str(telegram_id),
                "invoice_payload": invoice_payload,
                "provider": provider,
                "charge_id": charge_id,
                "currency": currency,
                "amount": amount,
            },
            telegram_id=telegram_id,
        )
        return VPNPaymentReceiptStatus(data["status"])

    async def get_status(self, *, telegram_id: str | int) -> VPNStatus:
        data = await self.backend.post(
            _STATUS_PATH,
            data={"username": str(telegram_id)},
            telegram_id=telegram_id,
        )
        return VPNStatus(
            status=VPNAccessStatus(data["status"]),
            expired_at=data.get("expired_at"),
            subscription_url=data.get("subscription_url"),
        )

    async def reissue(self, *, telegram_id: str | int) -> VPNAccessStatus:
        data = await self.backend.post(
            _REISSUE_PATH,
            data={"username": str(telegram_id)},
            telegram_id=telegram_id,
        )
        return VPNAccessStatus(data["status"])
