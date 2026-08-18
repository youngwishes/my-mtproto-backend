from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, final

from aiogram.types import LabeledPrice

if TYPE_CHECKING:
    from src.core.backend_client import BackendClient

_PRODUCT_PATH = "/api/v1/payments/"
_VPN_PRODUCT_PATH = "/api/v1/payments/products/vpn_30d/"
_BUY_PATH = "/api/v1/payments/buy/"
_GIFT_BUY_PATH = "/api/v1/payments/gift-certificates/buy/"
_GIFT_ACTIVATE_PATH = "/api/v1/payments/gift-certificates/activate/"
_CRYPTO_INVOICE_PATH = "/api/v1/payments/crypto/invoices/"
_PLATEGA_INVOICE_PATH = "/api/v1/payments/platega/invoices/"
_APPLE_STATUS_PATH = "/api/v1/payments/apples/status/"
_APPLE_REDEMPTION_PREVIEW_PATH = "/api/v1/payments/apples/redemptions/preview/"
_APPLE_REDEMPTION_CONFIRM_PATH = "/api/v1/payments/apples/redemptions/confirm/"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class StarsInvoice:
    title: str
    description: str
    prices: list[LabeledPrice]
    rub_amount: str
    payment_methods: tuple[str, ...]
    priority_payment_methods: tuple[str, ...]
    currency: str = "XTR"
    provider_token: str = ""


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class HistoricalPurchaseReplay:
    kind: Literal["historical_replay"] = "historical_replay"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ApplePurchaseOutcome:
    apples_earned: int
    rate_percent: int
    balance: int
    eligible_purchase_count: int
    level: str
    level_up: bool
    next_purchase_rate_percent: int


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ConfirmedPurchase:
    expired_date: str
    loyalty: ApplePurchaseOutcome


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class GiftCertificate:
    code: str
    loyalty: ApplePurchaseOutcome


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class AppleStatus:
    balance: int
    eligible_purchase_count: int
    level: str
    rate_percent: int
    next_level_purchase_count: int | None
    purchases_to_next_level: int | None
    is_max_level: bool
    redeemable_days: int
    missing_apples: int
    has_existing_key: bool


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class AppleRedemptionPreview:
    confirmation_id: int
    mode: str
    apples_spent: int
    days: int
    projected_expired_date: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class AppleRedemptionResult:
    apples_spent: int
    days: int
    expired_date: str
    balance: int


def _map_apple_purchase_outcome(data: dict) -> ApplePurchaseOutcome:
    return ApplePurchaseOutcome(
        apples_earned=data["apples_earned"],
        rate_percent=data["rate_percent"],
        balance=data["balance"],
        eligible_purchase_count=data["eligible_purchase_count"],
        level=data["level"],
        level_up=data["level_up"],
        next_purchase_rate_percent=data["next_purchase_rate_percent"],
    )


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ActivatedGiftCertificate:
    expired_date: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CryptoInvoice:
    invoice_url: str
    rub_amount: str
    expires_at: str
    reused: bool


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class PlategaInvoice:
    payment_url: str
    rub_amount: str
    expires_at: str
    reused: bool


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class PaymentsClient:
    backend: BackendClient

    async def get_stars_invoice(self) -> StarsInvoice:
        return await self._get_stars_invoice(path=_PRODUCT_PATH)

    async def get_vpn_stars_invoice(self) -> StarsInvoice:
        return await self._get_stars_invoice(path=_VPN_PRODUCT_PATH)

    async def _get_stars_invoice(self, *, path: str) -> StarsInvoice:
        data = await self.backend.get(path)
        return StarsInvoice(
            title=data["title"],
            description=data["description"],
            prices=[LabeledPrice(label=data["title"], amount=data["stars_price"])],
            rub_amount=str(data["rub_amount"]),
            payment_methods=tuple(str(code) for code in data["payment_methods"]),
            priority_payment_methods=tuple(
                str(code) for code in data["priority_payment_methods"]
            ),
        )

    async def confirm_purchase(
        self, *, telegram_id: str | int, charge_id: str, provider: str
    ) -> ConfirmedPurchase | HistoricalPurchaseReplay:
        response = await self.backend.post(
            _BUY_PATH,
            data={
                "username": str(telegram_id),
                "charge_id": charge_id,
                "provider": provider,
            },
            telegram_id=telegram_id,
        )
        if response == {"kind": "historical_replay"}:
            return HistoricalPurchaseReplay()
        return ConfirmedPurchase(
            expired_date=response["expired_date"],
            loyalty=_map_apple_purchase_outcome(response["loyalty"]),
        )

    async def confirm_gift_certificate_purchase(
        self, *, telegram_id: str | int, charge_id: str, provider: str
    ) -> GiftCertificate | HistoricalPurchaseReplay:
        response = await self.backend.post(
            _GIFT_BUY_PATH,
            data={
                "username": str(telegram_id),
                "charge_id": charge_id,
                "provider": provider,
            },
            telegram_id=telegram_id,
        )
        if response == {"kind": "historical_replay"}:
            return HistoricalPurchaseReplay()
        return GiftCertificate(
            code=response["code"],
            loyalty=_map_apple_purchase_outcome(response["loyalty"]),
        )

    async def get_apple_status(self, *, telegram_id: str | int) -> AppleStatus:
        response = await self.backend.post(
            _APPLE_STATUS_PATH,
            data={"username": str(telegram_id)},
            telegram_id=telegram_id,
        )
        return AppleStatus(**response)

    async def preview_apple_redemption(
        self, *, telegram_id: str | int, mode: str
    ) -> AppleRedemptionPreview:
        response = await self.backend.post(
            _APPLE_REDEMPTION_PREVIEW_PATH,
            data={"username": str(telegram_id), "mode": mode},
            telegram_id=telegram_id,
        )
        return AppleRedemptionPreview(**response)

    async def confirm_apple_redemption(
        self, *, telegram_id: str | int, confirmation_id: int
    ) -> AppleRedemptionResult:
        response = await self.backend.post(
            _APPLE_REDEMPTION_CONFIRM_PATH,
            data={
                "username": str(telegram_id),
                "confirmation_id": confirmation_id,
            },
            telegram_id=telegram_id,
        )
        return AppleRedemptionResult(**response)

    async def activate_gift_certificate(
        self, *, telegram_id: str | int, code: str
    ) -> ActivatedGiftCertificate:
        response = await self.backend.post(
            _GIFT_ACTIVATE_PATH,
            data={"username": str(telegram_id), "code": code},
            telegram_id=telegram_id,
        )
        return ActivatedGiftCertificate(**response)

    async def create_crypto_invoice(
        self, *, telegram_id: str | int, purchase_kind: str
    ) -> CryptoInvoice:
        response = await self.backend.post(
            _CRYPTO_INVOICE_PATH,
            data={"username": str(telegram_id), "purchase_kind": purchase_kind},
            telegram_id=telegram_id,
        )
        return CryptoInvoice(
            invoice_url=str(response["invoice_url"]),
            rub_amount=str(response["rub_amount"]),
            expires_at=str(response["expires_at"]),
            reused=bool(response["reused"]),
        )

    async def create_platega_invoice(
        self, *, telegram_id: str | int, purchase_kind: str
    ) -> PlategaInvoice:
        response = await self.backend.post(
            _PLATEGA_INVOICE_PATH,
            data={"username": str(telegram_id), "purchase_kind": purchase_kind},
            telegram_id=telegram_id,
        )
        return PlategaInvoice(
            payment_url=str(response["payment_url"]),
            rub_amount=str(response["rub_amount"]),
            expires_at=str(response["expires_at"]),
            reused=bool(response["reused"]),
        )
