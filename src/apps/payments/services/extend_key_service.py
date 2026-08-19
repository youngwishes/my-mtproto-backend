from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, final

from django.conf import settings
from django.db import transaction

from apps.payments.models import Payment

if TYPE_CHECKING:
    from apps.vds.models import MTPRotoKey


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ExtendKeyService:
    """Продлевает активный ключ на SUBSCRIPTION_PERIOD_DAYS дней.

    Отвязывает предыдущие платежи от ключа (key=NULL),
    чтобы новый Payment стал единственным владельцем связи.
    """

    def __call__(
        self,
        *,
        key: MTPRotoKey,
        reset_user_notified: bool = False,
    ) -> None:
        with transaction.atomic():
            key.expired_date += timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS)
            if reset_user_notified:
                key.user_notified = False
            key.save(update_fields=["expired_date", "user_notified"])
            Payment.objects.filter(key=key).update(key=None)


def get_extend_key_service() -> ExtendKeyService:
    return ExtendKeyService()
