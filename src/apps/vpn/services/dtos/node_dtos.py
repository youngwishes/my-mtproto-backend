from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, slots=True, frozen=True)
class NodeProfileDTO(BaseServiceDTO):
    """Профиль, который центральный backend передаёт VPN node-agent."""

    access_id: int
    vless_uuid: str
    hysteria_secret: str
