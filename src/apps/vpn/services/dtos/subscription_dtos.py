from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class SubscriptionProfileDTO(BaseServiceDTO):
    """Пара URI одного VPN-узла в subscription-конфигурации."""

    vless_uri: str
    hysteria2_uri: str
