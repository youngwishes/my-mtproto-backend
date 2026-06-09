from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

import requests
from django.conf import settings
from django.utils import html

from apps.core.telegram.transport import send_telegram_message
from apps.vds.selectors import get_keys_by_ids, get_vds_instance_by_id

if TYPE_CHECKING:
    from apps.vds.models import VDSInstance


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class RemoveKeysFromVdsInstanceInfraService:
    def __call__(self, *, server_id: int, keys_ids: list[int]) -> None:
        server = get_vds_instance_by_id(pk=server_id)
        keys = get_keys_by_ids(ids=keys_ids)
        usernames = list(keys.values_list("user__username", flat=True))
        try:
            response = requests.delete(
                url=f"{server.internal_url}/api/users",
                json={"usernames": usernames},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            keys.update(was_deleted=True, is_active=False)
        except Exception as exc:
            self._notify_admin(server=server, usernames=usernames, exc=exc)

    @staticmethod
    def _notify_admin(*, server: VDSInstance, usernames: list[str], exc: Exception) -> None:
        escaped_error = html.escape(str(exc))
        send_telegram_message(
            chat_id=int(settings.MY_TELEGRAM_ID),
            text=(
                "🔴 <b>(BACKEND) Системное оповещение</b>\n\n"
                "🛡 <b>Тип ошибки:</b> SERVER INTERNAL ERROR (500)\n"
                "📋 <b>Детали:</b>\n"
                f"- Не удалось удалить ключ пользователей с сервера\n"
                f"- Сервер — <b>{server.internal_url}</b>\n"
                f"- Порядковый номер сервера — <b>#{server.number}</b>\n"
                f"- Пользователи — <b>{usernames}</b>\n\n"
                f"<code>{escaped_error}</code>\n\n"
                "⚙️ <i>Требуется внимание команды!</i>"
            ),
        )


def get_remove_keys_from_vds_instance_infra_service() -> RemoveKeysFromVdsInstanceInfraService:
    return RemoveKeysFromVdsInstanceInfraService()
