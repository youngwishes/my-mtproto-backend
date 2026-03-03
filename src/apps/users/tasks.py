from celery import shared_task
from django.db import transaction

from apps.core.bot import TelegramBot
from apps.users.models import SystemUser
from apps.users.services import get_first_month_free_service
from apps.vds.models import MTPRotoKey


@shared_task
def send_free_link_to_user_task(telegram_id: str):
    with transaction.atomic():
        user = SystemUser.objects.get(username=telegram_id)
        MTPRotoKey.objects.filter(user=user).delete()
        link = get_first_month_free_service()(username=telegram_id).get("link")
        if not link:
            raise ValueError("Link not found. Link = %s" % link)
        TelegramBot.send_message_with_link(
            text=(
                "✨ *Привет!*\n\n"
                "Мы обновили наш сервис и сгенерировали для тебя новую ссылку на 1 месяц 🔥\n\n"
                "⚡️ Подключайся и проверяй — скорость теперь должна быть стабильной!\n\n"
                "👇 *Твоя ссылка:*"
            ),
            link=link,
            chat_id=telegram_id,
        )
        user.first_month_free_used = True
        user.save(update_fields=["first_month_free_used"])
