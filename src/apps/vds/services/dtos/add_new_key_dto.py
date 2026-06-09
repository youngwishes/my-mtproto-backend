from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class VDSKeyResponseOut(BaseServiceDTO):
    """Ответ VDS-сервера при создании/обновлении ключа."""

    key: str
    tls_domain: str
