from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class CreatePaymentIn(BaseServiceDTO):
    """Входные данные для создания платежа."""

    username: str
    charge_id: str
    provider: str
