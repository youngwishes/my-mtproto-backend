from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import TYPE_CHECKING, Protocol, final

from django.db import OperationalError, transaction

from apps.users.services.dtos import AcceptLegalConsentIn, LegalConsentOut

if TYPE_CHECKING:
    from apps.users.models import SystemUser

_SQLITE_LOCK_RETRY_COUNT = 5
_SQLITE_LOCK_RETRY_DELAY_SECONDS = 0.01


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
class AcceptLegalConsentService:
    """Атомарно и идемпотентно фиксирует единое юридическое согласие."""

    accept_user: _AcceptUser

    def __call__(self, *, data: AcceptLegalConsentIn) -> LegalConsentOut:
        for attempt in range(_SQLITE_LOCK_RETRY_COUNT):
            try:
                with transaction.atomic():
                    user = self.accept_user(
                        username=data.username,
                        telegram_username=data.telegram_username,
                        invited_from_username=data.invited_from_username,
                    )
                break
            except OperationalError as error:
                is_retryable_lock = "locked" in str(error).lower()
                is_last_attempt = attempt == _SQLITE_LOCK_RETRY_COUNT - 1
                if not is_retryable_lock or is_last_attempt:
                    raise
                sleep(_SQLITE_LOCK_RETRY_DELAY_SECONDS)

        return LegalConsentOut(
            legal_terms_accepted=user.legal_terms_accepted,
        )


def get_accept_legal_consent_service() -> AcceptLegalConsentService:
    from apps.users.selectors import accept_legal_terms

    return AcceptLegalConsentService(accept_user=accept_legal_terms)
