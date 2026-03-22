import time
from datetime import timedelta

import requests
from celery import shared_task
from django.conf import settings
from django.utils import html, timezone

from apps.core.bot import TelegramBot
from apps.vds.models import MTPRotoKey, VDSInstance


@shared_task
def remove_user_keys_daily():
    from apps.vds.services import get_remove_user_key_infra_service

    queryset = MTPRotoKey.objects.active().filter(
        expired_date__date__lte=timezone.now().date()
    )
    usernames = list(queryset.values_list("user__username", flat=True).distinct())
    if not usernames:
        return
    service = get_remove_user_key_infra_service()
    for server in VDSInstance.objects.all():
        service(server=server, keys=queryset)

    already_sent = set()
    for username in usernames:
        try:
            if username in already_sent:
                continue
            TelegramBot.send_message_deactivate_link(chat_id=username)
            already_sent.add(username)
            time.sleep(0.666)
        except Exception as exc:
            escaped_error = html.escape(exc)
            TelegramBot.send_message(
                chat_id=settings.MY_TELEGRAM_ID,
                text=(
                    "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                    "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                    "📋 <b>Детали:</b>\n"
                    f"- Не удалось уведомить пользователя об удалении ссылки\n"
                    f"- Пользователь — {username}\n\n"
                    f"<code>{escaped_error}</code>\n\n"
                    "⚙️ <i>Возможно, требуется внимание команды</i>"
                ),
            )


@shared_task
def notify_before_removing_daily():
    import time

    target_date = (timezone.now() + timedelta(days=1)).date()

    queryset = MTPRotoKey.objects.active().filter(
        expired_date__date=target_date,
        user_notified=False,
    )

    already_sent = set()
    for key in queryset:
        username = None
        try:
            username = getattr(key.user, "username", None)
            if not username:
                continue
            if username in already_sent:
                continue
            TelegramBot.notify_before_removing(chat_id=key.user.username)
            already_sent.add(username)
            key.user_notified = True
            key.save(update_fields=["user_notified"])
            time.sleep(0.666)
        except Exception as exc:
            escaped_error = html.escape(exc)
            TelegramBot.send_message(
                chat_id=settings.MY_TELEGRAM_ID,
                text=(
                    "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                    "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                    "📋 <b>Детали:</b>\n"
                    f"- Не удалось уведомить пользователя о завтрашнем удалении ссылки.\n"
                    f"- Пользователь — {username}\n\n"
                    f"<code>{escaped_error}</code>\n\n"
                    "⚙️ <i>Возможно, требуется внимание команды</i>"
                ),
            )


@shared_task
def add_key_to_another_vds_instances_task(exclude: int, username: str):
    servers = VDSInstance.objects.exclude(pk=exclude)
    for server in servers:
        try:
            response = requests.post(
                url=f"{server.internal_url}/api/v1/add-new-user",
                json={"username": username},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except Exception as exc:
            escaped_error = html.escape(exc)
            TelegramBot.send_message(
                chat_id=settings.MY_TELEGRAM_ID,
                text=(
                    "🔴 <b>(BACKEND) Системное оповещение</b>\n\n"
                    "🛡 <b>Тип ошибки:</b> SERVER INTERNAL ERROR (500)\n"
                    "📋 <b>Детали:</b>\n"
                    f"- Не удалось добавить пользователя на сервер\n"
                    f"- Сервер — <b>{server.internal_url}</b>\n"
                    f"- Порядковый номер сервера — <b>#{server.number}</b>\n"
                    f"- Пользователь — <b>{username}</b>\n\n"
                    f"<code>{escaped_error}</code>\n\n"
                    "⚙️ <i>Требуется внимание команды!</i>"
                ),
            )


@shared_task
def remove_key_from_another_vds_instances_task(
    server: VDSInstance, keys_id: list[int]
) -> None:
    keys = MTPRotoKey.objects.filter(pk__in=keys_id)
    usernames = keys.values_list("user__username", flat=True)
    try:
        response = requests.post(
            url=f"{server.internal_url}/api/v1/remove-user",
            json={"usernames": usernames},
            timeout=settings.VDS_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        keys.update(was_deleted=True, is_active=False)
    except Exception as exc:
        escaped_error = html.escape(exc)
        TelegramBot.send_message(
            chat_id=settings.MY_TELEGRAM_ID,
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
