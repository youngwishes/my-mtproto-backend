from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class LegalConsentStatusIn(BaseServiceDTO):
    username: str


@dataclass(kw_only=True, frozen=True, slots=True)
class AcceptLegalConsentIn(BaseServiceDTO):
    username: str
    telegram_username: str = ""
    invited_from_username: str | None = None


@dataclass(kw_only=True, frozen=True, slots=True)
class LegalConsentOut(BaseServiceDTO):
    legal_terms_accepted: bool
