from __future__ import annotations

from dataclasses import dataclass
from typing import final

from apps.core.decorators import log_service_error
from apps.users.selectors import get_user_by_username
from apps.vds.exceptions import KeyDoesNotExist
from apps.vds.selectors import get_active_key, get_all_active_vds_instances
from apps.vds.services.dtos import MyServerOut, MyServersOut


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class GetMyServersService:
    """Возвращает proxy-ссылки пользователя для всех активных VDS."""

    @log_service_error
    def __call__(self, *, username: str) -> MyServersOut:
        user = get_user_by_username(username=username)
        if user is None:
            raise KeyDoesNotExist(telegram_id=username)
        key = get_active_key(user=user)
        if key is None:
            raise KeyDoesNotExist(telegram_id=username)
        servers = [
            MyServerOut(
                location=vds.location,
                proxy_link=key.get_proxy_link(server_name=vds.name),
            )
            for vds in get_all_active_vds_instances()
        ]
        return MyServersOut(
            expired_date=key.expired_date.date().strftime("%d.%m.%y"),
            servers=servers,
        )


def get_my_servers_service() -> GetMyServersService:
    return GetMyServersService()
