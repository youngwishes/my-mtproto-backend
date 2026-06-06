from __future__ import annotations

import time
from time import sleep

from celery import shared_task
from django.conf import settings
from django.db import transaction

from apps.core.telegram.transport import is_channel_member, send_telegram_message
from apps.notifications.selectors import get_template
from apps.users.models import SystemUser
from apps.users.services import get_first_free_link_service
from apps.vds.models import MTPRotoKey


@shared_task
def send_invite_to_chat_task(telegram_ids: list[str]) -> None:
    if not telegram_ids:
        telegram_ids = SystemUser.objects.filter(
            first_month_free_used=True
        ).values_list("username", flat=True)
    template = get_template(slug="invite_to_channel")
    for user in telegram_ids:
        try:
            if not is_channel_member(telegram_id=int(user)):
                message = template.render()
                send_telegram_message(
                    chat_id=int(user),
                    text=message.text,
                    markup=message.markup,
                )
                sleep(0.666)
        except Exception:
            ...


@shared_task
def send_free_link_to_user_task(telegram_ids: list[str]) -> None:
    template = get_template(slug="proxy_link_with_message")
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

                message = template.render(
                    context={"text": text, "link": response.link},
                )
                send_telegram_message(
                    chat_id=int(telegram_id),
                    text=message.text,
                    markup=message.markup,
                    timeout=settings.TELEGRAM_TIMEOUT,
                )
                user.first_month_free_used = True
                if user.invited_from_username:
                    user.referral_activated = True
                user.save(update_fields=["first_month_free_used", "referral_activated"])
                time.sleep(0.666)
        except Exception:
            pass
