from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

import requests
from django.conf import settings
from django.utils import html

from apps.core.telegram.transport import send_telegram_message
from apps.vds.selectors import get_all_active_valid_keys, get_vds_instance_by_id

if TYPE_CHECKING:
    from apps.vds.models import MTPRotoKey, VDSInstance


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class SyncKeysToVdsInfraService:
    def __call__(self, *, instance_id: int) -> None:
        target = get_vds_instance_by_id(pk=instance_id)
        keys = get_all_active_valid_keys()

        for key in keys:
            if not getattr(key.user, "username", None) or not key.token:
                continue
            self._sync_key_to_server(key=key, target=target)

    def _sync_key_to_server(self, *, key: MTPRotoKey, target: VDSInstance) -> None:
        try:
            response = requests.post(
                url=f"{target.internal_url}/api/users",
                json={"username": key.user.username, "secret": key.token},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except Exception as exc:
            self._notify_admin(key=key, target=target, exc=exc)

    @staticmethod
    def _notify_admin(*, key: MTPRotoKey, target: VDSInstance, exc: Exception) -> None:
        escaped_error = html.escape(str(exc))
        send_telegram_message(
            chat_id=int(settings.MY_TELEGRAM_ID),
            text=(
                "🔴 <b>(BACKEND) Системное оповещение</b>\n\n"
                "🛡 <b>Тип ошибки:</b> SERVER INTERNAL ERROR (500)\n"
                "📋 <b>Детали:</b>\n"
                f"- Не удалось синхронизировать ключ на сервер\n"
                f"- Сервер — <b>{target.internal_url}</b>\n"
                f"- Порядковый номер сервера — <b>#{target.number}</b>\n"
                f"- Пользователь — <b>{key.user.username}</b>\n"
                f"- Ключ — <b>{key}</b>\n\n"
                f"<code>{escaped_error}</code>\n\n"
                "⚙️ <i>Требуется внимание команды!</i>"
            ),
        )


def get_sync_keys_to_vds_infra_service() -> SyncKeysToVdsInfraService:
    return SyncKeysToVdsInfraService()
