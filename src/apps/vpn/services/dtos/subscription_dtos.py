from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class SubscriptionProfileDTO(BaseServiceDTO):
    """Пара URI одного VPN-узла в subscription-конфигурации."""

    vless_uri: str
    hysteria2_uri: str


@dataclass(kw_only=True, frozen=True, slots=True)
class VPNReissueOut(BaseServiceDTO):
    """Результат перевыпуска с неизменным сроком и новой subscription URL."""

    expired_at: datetime
    subscription_url: str
