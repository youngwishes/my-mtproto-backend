from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from aiogram.types import LabeledPrice

if TYPE_CHECKING:
    from src.core.backend_client import BackendClient

_PRODUCT_PATH = "/api/v1/payments/"
_VPN_PRODUCT_PATH = "/api/v1/payments/products/vpn_30d/"
_BUY_PATH = "/api/v1/payments/buy/"
_GIFT_BUY_PATH = "/api/v1/payments/gift-certificates/buy/"
_GIFT_ACTIVATE_PATH = "/api/v1/payments/gift-certificates/activate/"
_CRYPTO_INVOICE_PATH = "/api/v1/payments/crypto/invoices/"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class StarsInvoice:
    title: str
    description: str
    prices: list[LabeledPrice]
    payment_methods: tuple[str, ...]
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
class CryptoInvoice:
    invoice_url: str
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
            payment_methods=tuple(str(code) for code in data["payment_methods"]),
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
