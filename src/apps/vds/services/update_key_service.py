from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import final

from django.db import transaction
from django.utils import timezone

from apps.core.decorators import log_service_error
from apps.users.selectors import get_user_by_username
from apps.vds.exceptions import KeyDoesNotExist, TooManyRequests
from apps.vds.selectors import get_active_key, get_keys_by_username, get_least_populated_vds
from apps.vds.services import get_update_key_infra_service
from apps.vds.services.dtos import UpdateKeyOut


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class UpdateKeyService:
    @log_service_error
    def __call__(self, *, username: str) -> UpdateKeyOut | None:
        user = get_user_by_username(username=username)
        if user is None:
            raise KeyDoesNotExist(telegram_id=username)
        key = get_active_key(user=user)
        if key is None:
            raise KeyDoesNotExist(telegram_id=username)

        if key.last_update and (
            key.last_update + timedelta(minutes=5) > timezone.now()
        ):
            raise TooManyRequests(telegram_id=username)

        with transaction.atomic():
            server = get_least_populated_vds()
            infra = get_update_key_infra_service()
            response = infra(username=username, server=server)

            key.vds = server
            key.token = response.key
            key.tls_domain = response.tls_domain
            key.node_number = server.name
            key.last_update = timezone.now()
            key.was_deleted = False
            key.is_active = True
            key.save(
                update_fields=[
                    "token",
                    "tls_domain",
                    "node_number",
                    "vds",
                    "last_update",
                    "was_deleted",
                    "is_active",
                ]
            )

            get_keys_by_username(username=username).exclude(pk=key.pk).delete()

        return UpdateKeyOut(
            link=key.get_proxy_link(),
            expired_date=key.expired_date.date().strftime("%d.%m.%y"),
        )


def get_update_key_service() -> UpdateKeyService:
    return UpdateKeyService()
