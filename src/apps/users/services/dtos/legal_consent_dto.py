from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class LegalConsentStatusIn(BaseServiceDTO):
    """Входные данные read-only проверки согласия."""

    username: str


@dataclass(kw_only=True, frozen=True, slots=True)
class AcceptLegalConsentIn(BaseServiceDTO):
    """Данные пользователя, сохраняемые только при принятии согласия."""

    username: str
    telegram_username: str = ""
    invited_from_username: str | None = None


@dataclass(kw_only=True, frozen=True, slots=True)
class LegalConsentOut(BaseServiceDTO):
    """Сохранённый статус юридического согласия."""

    legal_terms_accepted: bool
