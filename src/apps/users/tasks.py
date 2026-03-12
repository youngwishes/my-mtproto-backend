import time
from time import sleep

from celery import shared_task
from django.db import transaction

from apps.core.bot import TelegramBot
from apps.users.models import SystemUser
from apps.users.services import get_first_free_link_service
from apps.vds.models import MTPRotoKey


@shared_task
def send_invite_to_chat_task() -> None:
    users = SystemUser.objects.filter(first_month_free_used=True).values_list(
        "username", flat=True
    )
    for user in users:
        try:
            is_channel_member = TelegramBot.is_channel_member(telegram_id=int(user))
            if not is_channel_member:
                TelegramBot.send_invite_to_chat(telegram_id=int(user))
                sleep(0.666)
        except Exception:
            ...


@shared_task
def send_test_invite_to_chat_task() -> None:
    users = SystemUser.objects.filter(username="8169923535").values_list(
        "username", flat=True
    )
    for user in users:
        try:
            is_channel_member = TelegramBot.is_channel_member(telegram_id=int(user))
            if not is_channel_member:
                TelegramBot.send_invite_to_chat(telegram_id=int(user))
                sleep(0.666)
        except Exception:
            ...


@shared_task
def send_free_link_to_user_task(telegram_ids: list[str]) -> None:
    for telegram_id in telegram_ids:
        with transaction.atomic():
            user = SystemUser.objects.get(username=telegram_id)
            if user.first_month_free_used:
                continue
            MTPRotoKey.objects.filter(user=user).delete()
            response = get_first_free_link_service()(username=telegram_id)
            if not response.link:
                raise ValueError("Link not found. Link = %s" % response.link)

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
            user.save(update_fields=["first_month_free_used"])
            time.sleep(0.666)
