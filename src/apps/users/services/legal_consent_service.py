from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, final

from apps.users.services.dtos import (
    AcceptLegalConsentIn,
    LegalConsentOut,
    LegalConsentStatusIn,
)

if TYPE_CHECKING:
    from apps.users.models import SystemUser


class _GetUser(Protocol):
    def __call__(self, *, username: str) -> SystemUser | None: ...


class _AcceptUser(Protocol):
    def __call__(
        self,
        *,
        username: str,
        telegram_username: str,
        invited_from_username: str | None,
    ) -> SystemUser: ...


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class GetLegalConsentStatusService:
    """Read-only возвращает сохранённый статус согласия."""

    get_user: _GetUser

    def __call__(self, *, data: LegalConsentStatusIn) -> LegalConsentOut:
        user = self.get_user(username=data.username)
        return LegalConsentOut(
            legal_terms_accepted=bool(
                user is not None and user.legal_terms_accepted
            )
        )


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class AcceptLegalConsentService:
    """Идемпотентно сохраняет единое юридическое согласие."""

    accept_user: _AcceptUser

    def __call__(self, *, data: AcceptLegalConsentIn) -> LegalConsentOut:
        user = self.accept_user(
            username=data.username,
            telegram_username=data.telegram_username,
            invited_from_username=data.invited_from_username,
        )
        return LegalConsentOut(
            legal_terms_accepted=user.legal_terms_accepted
        )


def get_legal_consent_status_service() -> GetLegalConsentStatusService:
    from apps.users.selectors import get_user_by_username

    return GetLegalConsentStatusService(get_user=get_user_by_username)


def get_accept_legal_consent_service() -> AcceptLegalConsentService:
    from apps.users.selectors import accept_legal_terms

    return AcceptLegalConsentService(accept_user=accept_legal_terms)
