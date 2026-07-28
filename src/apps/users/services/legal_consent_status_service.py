from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, final

from apps.users.services.dtos import LegalConsentOut, LegalConsentStatusIn

if TYPE_CHECKING:
    from apps.users.models import SystemUser


class _GetUserByUsername(Protocol):
    def __call__(self, *, username: str) -> SystemUser | None: ...


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class GetLegalConsentStatusService:
    """Возвращает consent без создания или обновления пользователя."""

    get_user: _GetUserByUsername

    def __call__(self, *, data: LegalConsentStatusIn) -> LegalConsentOut:
        user = self.get_user(username=data.username)
        return LegalConsentOut(
            legal_terms_accepted=bool(
                user is not None and user.legal_terms_accepted
            ),
        )


def get_legal_consent_status_service() -> GetLegalConsentStatusService:
    from apps.users.selectors import get_user_by_username

    return GetLegalConsentStatusService(get_user=get_user_by_username)
