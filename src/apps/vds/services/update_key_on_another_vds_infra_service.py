from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

import requests
from django.conf import settings
from django.utils import html

from apps.core.telegram.transport import send_telegram_message
from apps.vds.selectors import get_other_active_vds_instances

if TYPE_CHECKING:
    from apps.vds.models import VDSInstance


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class UpdateKeyOnAnotherVdsInfraService:
    def __call__(self, *, exclude: int, username: str, secret: str) -> None:
        servers = get_other_active_vds_instances(exclude_pk=exclude)
        for server in servers:
            self._update_key_on_server(server=server, username=username, secret=secret)

    def _update_key_on_server(self, *, server: VDSInstance, username: str, secret: str) -> None:
        try:
            response = requests.patch(
                url=f"{server.internal_url}/api/users",
                json={"username": username, "secret": secret},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except Exception as exc:
            self._notify_admin(server=server, username=username, exc=exc)

    @staticmethod
    def _notify_admin(*, server: VDSInstance, username: str, exc: Exception) -> None:
        escaped_error = html.escape(str(exc))
        send_telegram_message(
            chat_id=int(settings.MY_TELEGRAM_ID),
            text=(
                "🔴 <b>(BACKEND) Системное оповещение</b>\n\n"
                "🛡 <b>Тип ошибки:</b> SERVER INTERNAL ERROR (500)\n"
                "📋 <b>Детали:</b>\n"
                f"- Не удалось обновить ключ на сервере\n"
                f"- Сервер — <b>{server.internal_url}</b>\n"
                f"- Порядковый номер сервера — <b>#{server.number}</b>\n"
                f"- Пользователь — <b>{username}</b>\n\n"
                f"<code>{escaped_error}</code>\n\n"
                "⚙️ <i>Требуется внимание команды!</i>"
            ),
        )


def get_update_key_on_another_vds_instances_service() -> UpdateKeyOnAnotherVdsInfraService:
    return UpdateKeyOnAnotherVdsInfraService()
