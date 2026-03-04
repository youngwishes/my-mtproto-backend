from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.core.bot import TelegramBot
from apps.vds.models import MTPRotoKey


@shared_task
def remove_user_keys_daily():
    import time

    from apps.vds.services import get_remove_user_key_service

    one_month_ago = timezone.now() - timedelta(days=30)
    queryset = MTPRotoKey.objects.active().filter(created_at__lt=one_month_ago)
    if not queryset:
        return
    service = get_remove_user_key_service()
    service(keys=queryset)

    already_sent = set()

    for key in queryset:
        username = None
        try:
            username = getattr(key.user, "username", None)
            if not username:
                continue
            if username in already_sent:
                continue
            TelegramBot.send_message_deactivate_link(chat_id=key.user.username)
            already_sent.add(username)
            time.sleep(0.666)
        except Exception as exc:
            TelegramBot.send_message(
                chat_id=settings.MY_TELEGRAM_ID,
                text=(
                    f"Не удалось уведомить пользователя о просроченной ссылке\n\n"
                    f"error={exc}\n\n"
                    f"telegram_id={username}"
                ),
            )


@shared_task
def notify_before_removing_daily():
    import time

    target_date = (timezone.now() - timedelta(days=29)).date()

    queryset = MTPRotoKey.objects.active().filter(
        created_at__date=target_date,
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
            TelegramBot.send_message(
                chat_id=settings.MY_TELEGRAM_ID,
                text=(
                    f"Не удалось уведомить пользователя о просроченной ссылке\n\n"
                    f"error={exc}\n\n"
                    f"telegram_id={username}"
                ),
            )
