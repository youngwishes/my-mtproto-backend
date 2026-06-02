from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.bot import TelegramBot
from apps.core.service import log_service_error
from apps.payments.models import Payment
from apps.users.models import SystemUser
from apps.vds.models import MTPRotoKey
from apps.vds.services import get_issue_key_service


@dataclass(kw_only=True, slots=True, frozen=True)
class CreatePaymentService:
    @log_service_error
    def __call__(self, *, username: str, charge_id: str, provider: str) -> None:
        user, _ = SystemUser.objects.get_or_create(username=username)

        active_key = user.keys.filter(
            was_deleted=False,
            expired_date__gt=timezone.now(),
        ).first()

        if active_key:
            self._extend_key(
                user=user,
                key=active_key,
                charge_id=charge_id,
                provider=provider,
            )
        else:
            self._issue_new_key(
                user=user,
                charge_id=charge_id,
                provider=provider,
            )

    def _extend_key(
        self,
        *,
        user: SystemUser,
        key: MTPRotoKey,
        charge_id: str,
        provider: str,
    ) -> None:
        with transaction.atomic():
            key.expired_date += timedelta(days=30)
            key.save(update_fields=["expired_date"])
            Payment.objects.filter(key=key).update(key=None)
            Payment.objects.create(
                user=user,
                key=key,
                charge_id=charge_id,
                provider=provider,
            )
        TelegramBot.send_proxy_link(
            chat_id=user.username,
            link=key.get_proxy_link(),
        )

    def _issue_new_key(self, *, user: SystemUser, charge_id: str, provider: str) -> None:
        with transaction.atomic():
            mtproto_key = get_issue_key_service()(
                user=user,
                expired_date=timezone.now() + timedelta(days=30),
            )
            Payment.objects.create(
                user=user,
                key=mtproto_key,
                charge_id=charge_id,
                provider=provider,
            )
        TelegramBot.send_proxy_link(
            chat_id=user.username,
            link=mtproto_key.get_proxy_link(),
        )


def get_create_payment_service() -> CreatePaymentService:
    return CreatePaymentService()
