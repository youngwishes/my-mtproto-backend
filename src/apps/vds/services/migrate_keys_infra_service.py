from __future__ import annotations

from dataclasses import dataclass
from typing import final

import requests
from django.conf import settings
from django.utils import html

from apps.core.telegram.transport import send_telegram_message
from apps.vds.models import VDSInstance
from apps.vds.selectors import get_other_active_vds_instances, get_vds_instance_by_id, get_vds_instance_keys


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class MigrateVdsKeysInfraService:
    def __call__(self, *, from_instance_id: int) -> None:
        source = get_vds_instance_by_id(pk=from_instance_id)
        keys = get_vds_instance_keys(instance=source)
        target_servers = get_other_active_vds_instances(exclude_pk=from_instance_id)

        for key in keys:
            if not getattr(key.user, "username", None) or not key.token:
                continue

            if key.was_deleted or (not key.is_active):
                continue

            for target in target_servers:
                self._migrate_key_to_server(key=key, target=target)

    def _migrate_key_to_server(self, *, key, target: VDSInstance) -> None:
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
    def _notify_admin(*, key, target: VDSInstance, exc: Exception) -> None:
        escaped_error = html.escape(str(exc))
        send_telegram_message(
            chat_id=int(settings.MY_TELEGRAM_ID),
            text=(
                "🔴 <b>(BACKEND) Системное оповещение</b>\n\n"
                "🛡 <b>Тип ошибки:</b> SERVER INTERNAL ERROR (500)\n"
                "📋 <b>Детали:</b>\n"
                f"- Не удалось перенести ключ на сервер\n"
                f"- Сервер — <b>{target.internal_url}</b>\n"
                f"- Порядковый номер сервера — <b>#{target.number}</b>\n"
                f"- Пользователь — <b>{key.user.username}</b>\n"
                f"- Ключ — <b>{key}</b>\n\n"
                f"<code>{escaped_error}</code>\n\n"
                "⚙️ <i>Требуется внимание команды!</i>"
            ),
        )


def get_migrate_vds_keys_service() -> MigrateVdsKeysInfraService:
    return MigrateVdsKeysInfraService()
