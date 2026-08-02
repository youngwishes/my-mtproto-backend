from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, slots=True, frozen=True)
class CryptoInvoiceDTO(BaseServiceDTO):
    """Нормализованные данные счёта Crypto Pay."""

    invoice_id: int
    status: str
    currency_type: str
    fiat: str | None
    amount: Decimal
    accepted_assets: frozenset[str]
    paid_asset: str | None
    payload: str
    bot_invoice_url: str
    created_at: datetime
    expiration_date: datetime
    paid_at: datetime | None


@dataclass(kw_only=True, slots=True, frozen=True)
class CreateCryptoInvoiceIn(BaseServiceDTO):
    """Входные данные для счёта Crypto Pay."""

    username: str
    purchase_kind: str


@dataclass(kw_only=True, slots=True, frozen=True)
class CreateCryptoInvoiceOut(BaseServiceDTO):
    """Безопасный результат создания счёта для bot boundary."""

    invoice_url: str
    rub_amount: Decimal
    expires_at: datetime
    reused: bool


@dataclass(kw_only=True, slots=True, frozen=True)
class ValidatedCryptoPaymentDTO(BaseServiceDTO):
    """Проверенный счёт, привязанный к payment intent."""

    intent_id: int
    invoice: CryptoInvoiceDTO


@dataclass(kw_only=True, slots=True, frozen=True)
class CryptoWebhookWarningDTO(BaseServiceDTO):
    """Безопасный контекст отклонённого webhook-события."""

    reason: str
    update_id: int | None
    invoice_id: int | None
    intent_id: int | None


@dataclass(kw_only=True, slots=True, frozen=True)
class ApplyCryptoPaymentOut(BaseServiceDTO):
    """Результат идемпотентного применения Crypto Pay платежа."""

    fulfilled: bool
    already_fulfilled: bool
