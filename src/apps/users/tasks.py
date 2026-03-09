from time import sleep

from celery import shared_task
from django.db import transaction

from apps.core.bot import TelegramBot
from apps.users.models import SystemUser
from apps.users.services import get_first_free_link_service
from apps.vds.models import MTPRotoKey


@shared_task
def send_free_link_to_user_task(telegram_id: str):
    with transaction.atomic():
        user = SystemUser.objects.get(username=telegram_id)
        MTPRotoKey.objects.filter(user=user).delete()
        link = get_first_free_link_service()(username=telegram_id).link
        if not link:
            raise ValueError("Link not found. Link = %s" % link)

        text = (
            "✨ <b>Привет!</b>\n\n"
            "🔥 Мы обновили наш сервис и сгенерировали для тебя новую ссылку <b>на 1 месяц</b> \n\n"
            "⚡️ Подключайся и проверяй — скорость теперь должна быть стабильной!\n\n"
            "👀 Пожалуйста, подпишись на канал @mtproto_keys — там вся информация по развитию проекта\n\n"
            "👇 <b>Твоя ссылка:</b>"
        )

        TelegramBot.send_message_with_link(
            text=text,
            link=link,
            chat_id=telegram_id,
        )
        user.first_month_free_used = True
        user.save(update_fields=["first_month_free_used"])


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
