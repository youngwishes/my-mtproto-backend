from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, final

if TYPE_CHECKING:
    from src.core.backend_client import BackendClient

_MENU_PATH = "/api/v1/vpn/menu/?username={telegram_id}"
_BUY_PATH = "/api/v1/vpn/payments/buy/"
_REISSUE_PATH = "/api/v1/vpn/reissue/"
_PRODUCT_CODE = "vpn_30d"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNMenu:
    status: Literal["none", "active", "expired"]
    expired_at: str | None
    subscription_url: str | None


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNPurchase:
    expired_at: str
    subscription_url: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNReissue:
    expired_at: str
    subscription_url: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNClient:
    backend: BackendClient

    async def get_menu(self, *, telegram_id: str | int) -> VPNMenu:
        response = await self.backend.get(
            _MENU_PATH.format(telegram_id=telegram_id),
            telegram_id=telegram_id,
        )
        return VPNMenu(**response)

    async def confirm_purchase(
        self, *, telegram_id: str | int, charge_id: str, provider: str
    ) -> VPNPurchase:
        response = await self.backend.post(
            _BUY_PATH,
            data={
                "username": str(telegram_id),
                "charge_id": charge_id,
                "provider": provider,
                "product_code": _PRODUCT_CODE,
            },
            telegram_id=telegram_id,
        )
        return VPNPurchase(**response)

    async def reissue(self, *, telegram_id: str | int) -> VPNReissue:
        response = await self.backend.post(
            _REISSUE_PATH,
            data={"username": str(telegram_id)},
            telegram_id=telegram_id,
        )
        return VPNReissue(**response)
