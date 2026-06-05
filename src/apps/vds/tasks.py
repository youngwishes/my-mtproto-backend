import time
from datetime import timedelta

import requests
from celery import shared_task
from django.conf import settings
from django.utils import html, timezone

from apps.core.bot import TelegramBot, bot
from apps.vds.models import MTPRotoKey, VDSInstance


@shared_task
def migrate_vds_keys_task(from_instance_id: int) -> None:
    server = VDSInstance.objects.get(pk=from_instance_id)
    keys = server.keys.all().select_related("user")
    for key in keys:
        for server in VDSInstance.objects.exclude(pk=from_instance_id):
            try:
                if not getattr(key.user, "username", None):
                    continue
                if not key.token:
                    continue
                requests.post(
                    url=f"{server.internal_url}/api/users",
                    json={"username": key.user.username, "secret": key.token},
                    timeout=settings.VDS_REQUEST_TIMEOUT,
                )
            except Exception as exc:
                escaped_error = html.escape(exc)
                TelegramBot.send_message(
                    chat_id=settings.MY_TELEGRAM_ID,
                    text=(
                        "🔴 <b>(BACKEND) Системное оповещение</b>\n\n"
                        "🛡 <b>Тип ошибки:</b> SERVER INTERNAL ERROR (500)\n"
                        "📋 <b>Детали:</b>\n"
                        f"- Не удалось добавить перенести ключ на сервер\n"
                        f"- Сервер — <b>{server.internal_url}</b>\n"
                        f"- Порядковый номер сервера — <b>#{server.number}</b>\n"
                        f"- Пользователь — <b>{key.user.username}</b>\n"
                        f"- Ключ — <b>{key}</b>\n\n"
                        f"<code>{escaped_error}</code>\n\n"
                        "⚙️ <i>Требуется внимание команды!</i>"
                    ),
                )

        time.sleep(0.5)


@shared_task
def remove_user_keys_daily():
    from apps.vds.services import get_remove_user_key_infra_service

    queryset = MTPRotoKey.objects.active().expired_today()
    usernames = list(queryset.values_list("user__username", flat=True).distinct())
    if not usernames:
        return
    service = get_remove_user_key_infra_service()
    for server in VDSInstance.objects.all():
        service(server=server, keys=queryset)
    queryset.update(is_active=False, was_deleted=True)
    for username in usernames:
        try:
            TelegramBot.send_message_deactivate_link(chat_id=username)
            time.sleep(1)
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
            time.sleep(1)
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
def notify_before_removing_daily_hour_before():
    queryset = MTPRotoKey.objects.active().filter(expired_date__date=timezone.now().date())

    already_sent = set()
    for key in queryset:
        username = None
        try:
            username = getattr(key.user, "username", None)
            if not username:
                continue
            if username in already_sent:
                continue
            TelegramBot.notify_before_removing_before_hour(chat_id=key.user.username)
            already_sent.add(username)
            time.sleep(1)
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
def add_key_to_another_vds_instances_task(exclude: int, username: str, secret: str):
    servers = VDSInstance.objects.exclude(pk=exclude)
    for server in servers:
        try:
            response = requests.post(
                url=f"{server.internal_url}/api/users",
                json={"username": username, "secret": secret},
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
def remove_key_from_another_vds_instances_task(server: int, keys_id: list[int]) -> None:
    server = VDSInstance.objects.get(pk=server)
    keys = MTPRotoKey.objects.filter(pk__in=keys_id)
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


@shared_task
def broadcast_proxy_links_task(testing: bool = False) -> None:
    from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

    if testing:
        keys = MTPRotoKey.objects.filter(
            user__pk=562,
            is_active=True,
            was_deleted=False,
        ).select_related("user")
    else:
        keys = (
            MTPRotoKey.objects.filter(
                is_active=True,
                was_deleted=False,
                user__first_month_free_used=True,
                expired_date__gt=timezone.now(),
            )
            .select_related("user")
        )

    sent_count = 0
    for key in keys:
        try:
            bot.send_message(
                chat_id=key.user.username,
                text=(
                    "✨ <b>Привет!</b>\n\n"
                    "В последнее время часть ссылок могла работать нестабильно из-за блокировок. "
                    "Мы долго работали над решением — и нам удалось <b>полностью обойти ограничения.</b>\n\n"
                    "Сейчас всё работает стабильно, и мы решили продлить твою ссылку на <b>3 дня</b> "
                    "в качестве компенсации за неудобства.\n\n"
                    f"👇 <b>Твоя ссылка (действует до {(key.expired_date + timedelta(days=3)).strftime('%d.%m.%Y')}):</b>"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🇳🇱 Подключиться",
                                url=key.get_proxy_link(),
                                callback_data=None,
                                style="primary",
                            )
                        ]
                    ]
                ),
            )
            key.expired_date = key.expired_date + timedelta(days=3)
            key.save(update_fields=["expired_date"])
            sent_count += 1
            if sent_count % 10 == 0:
                time.sleep(1)
        except Exception as exc:
            try:
                escaped_error = html.escape(str(exc))
                bot.send_message(
                    chat_id=settings.MY_TELEGRAM_ID,
                    text=(
                        "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                        "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                        "📋 <b>Детали:</b>\n"
                        f"- Не удалось отправить broadcast пользователю\n"
                        f"- Пользователь — {key.user.username}\n\n"
                        f"<code>{escaped_error}</code>\n\n"
                        "⚙️ <i>Возможно, требуется внимание команды</i>"
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
