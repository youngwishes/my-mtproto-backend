import os
import time
from time import sleep

import requests
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import html

from apps.core.bot import TelegramBot
from apps.users.models import SystemUser
from apps.users.services import get_first_free_link_service
from apps.vds.models import MTPRotoKey, VDSInstance


@shared_task
def send_new_link(telegram_ids: list[str]) -> None:
    keys = (
        MTPRotoKey.objects.exclude(
            tls_domain="beatvault.ru",
        )
        .filter(is_active=True, was_deleted=False, user__new_link_sent=False)
        .select_related("user")
    )

    if telegram_ids:
        users = SystemUser.objects.filter(username__in=telegram_ids, new_link_sent=False)
        if users.exists():
            keys.filter(user__username__in=telegram_ids)

    target_server = VDSInstance.objects.get(pk=9)
    for key in keys:
        try:
            secret = str(os.urandom(16).hex())
            response = requests.post(
                url=f"{target_server.internal_url}/api/v1/add-new-user",
                json={"username": key.user.username, "secret": secret},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            text = (
                "✨ <b>Привет!</b>\n\n"
                "🔥 Мы постоянно развиваем сервис и выпустили ссылки нового образца, которые работают стабильнее!\n\n"
                "👀 ВАЖНО! Используй новую ссылку, которая прикреплена <b>в этом сообщении!</b>\n\n"
                "Та ссылка по которой ты подключаешься сейчас скоро <b>перестанет работать!</b>\n\n"
                "👇 <b>Твоя новая ссылка сроком действия до {expired_date}:</b>"
            ).format(expired_date=key.expired_date)
            TelegramBot.send_message_with_link(
                text=text,
                link=key.get_proxy_link(),
                chat_id=key.user.username,
            )
            with transaction.atomic():
                key.tls_domain = response.json()["tls_domain"]
                key.token = secret
                key.node_number = response.json()["node_number"]
                key.save(update_fields=["tls_domain", "token", "node_number"])
                key.user.new_link_sent = True
                key.user.save(update_fields=["new_link_sent"])
        except Exception as exc:
            escaped_error = html.escape(exc)
            TelegramBot.send_message(
                chat_id=settings.MY_TELEGRAM_ID,
                text=(
                    "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                    "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                    "📋 <b>Детали:</b>\n"
                    f"- Не удалось уведомить пользователя об удалении ссылки\n"
                    f"- Пользователь — {key.user.username}\n\n"
                    f"<code>{escaped_error}</code>\n\n"
                    "⚙️ <i>Возможно, требуется внимание команды</i>"
                ),
            )
        else:
            TelegramBot.send_message(
                chat_id=settings.MY_TELEGRAM_ID,
                text=(
                    "🟢 <b>(BACKEND) Системное оповещение</b>\n\n"
                    "🛡 <b>Тип события:</b> уведомление\n"
                    "📋 <b>Детали:</b>\n"
                    f"- Ссылка нового формата успешно отправлена пользователю\n"
                    f"- Пользователь — {key.user.username}\n\n"
                ),
            )
        finally:
            sleep(0.25)



@shared_task
def send_invite_to_chat_task(telegram_ids: list[str]) -> None:
    if not telegram_ids:
        telegram_ids = SystemUser.objects.filter(
            first_month_free_used=True
        ).values_list("username", flat=True)
    for user in telegram_ids:
        try:
            is_channel_member = TelegramBot.is_channel_member(telegram_id=int(user))
            if not is_channel_member:
                TelegramBot.send_invite_to_chat_v2(telegram_id=int(user))
                sleep(0.666)
        except Exception:
            ...


@shared_task
def send_free_link_to_user_task(telegram_ids: list[str]) -> None:
    for telegram_id in telegram_ids:
        user = SystemUser.objects.get(username=telegram_id)
        if user.first_month_free_used:
            continue
        try:
            with transaction.atomic():
                MTPRotoKey.objects.filter(user=user).delete()
                response = get_first_free_link_service()(username=telegram_id)

                text = (
                    "✨ <b>Привет!</b>\n\n"
                    "🔥 Мы сгенерировали для тебя ссылку сроком действия до <b>{expired_date}</b> \n\n"
                    "⚡️ Попробуй — с ней мессенджер работает быстрее!\n\n"
                    "👀 Пожалуйста, подпишись на канал @mtproto_keys — там вся информация по развитию проекта\n\n"
                    "👇 <b>Твоя ссылка:</b>"
                ).format(expired_date=response.expired_date)

                TelegramBot.send_message_with_link(
                    text=text,
                    link=response.link,
                    chat_id=telegram_id,
                )
                user.first_month_free_used = True
                if user.invited_from_username:
                    user.referral_activated = True
                user.save(update_fields=["first_month_free_used", "referral_activated"])
                time.sleep(0.666)
        except Exception:
            pass


@shared_task
def update_user_link_task(telegram_ids: list[str]) -> None:
    for telegram_id in telegram_ids:
        TelegramBot.update_user_link_notification(telegram_id=int(telegram_id))
        time.sleep(0.666)
