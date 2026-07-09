from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class CreateGiftCertificateIn(BaseServiceDTO):
    """Входные данные для покупки подарочного сертификата."""

    username: str
    charge_id: str
    provider: str


@dataclass(kw_only=True, frozen=True, slots=True)
class CreateGiftCertificateOut(BaseServiceDTO):
    """Результат покупки подарочного сертификата."""

    code: str


@dataclass(kw_only=True, frozen=True, slots=True)
class ActivateGiftCertificateIn(BaseServiceDTO):
    """Входные данные для активации подарочного сертификата."""

    username: str
    code: str


@dataclass(kw_only=True, frozen=True, slots=True)
class ActivateGiftCertificateOut(BaseServiceDTO):
    """Результат активации подарочного сертификата."""

    expired_date: str
