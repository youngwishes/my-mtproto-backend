from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, slots=True, frozen=True)
class FulfillVPNPaymentIn(BaseServiceDTO):
    """Данные успешной оплаты VPN-подписки."""

    username: str
    charge_id: str
    provider: str
    product_code: str


@dataclass(kw_only=True, slots=True, frozen=True)
class VPNPurchaseOut(BaseServiceDTO):
    """Срок доступа и постоянная внешняя subscription-ссылка."""

    expired_at: datetime
    subscription_url: str
