from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class SystemUser(AbstractUser):
    first_month_free_used = models.BooleanField(
        "бесплатный месяц использован", default=False
    )
    telegram_username = models.CharField(
        "имя пользователя в Telegram",
        blank=True,
    )
    invited_from_username = models.CharField(
        "TG-ID от кого пришел пользователь",
        blank=True,
        null=True,
    )
    referral_activated = models.BooleanField(
        "реферал активирован",
        default=False,
    )
    referral_link_activated_count = models.PositiveSmallIntegerField(
        "количество активированных реф. ссылок",
        default=0,
    )
    notified_update_link = models.BooleanField(
        "уведомлен о возможности перевыпуска",
        default=False,
    )
    new_link_sent = models.BooleanField(
        "отправлена новая ссылка вида space.beatvault.ru",
        default=False,
    )
    is_agree = models.BooleanField(
        "согласен с публикацией в канале",
        default=False,
    )

    @property
    def referral_link(self) -> str:
        return settings.BOT_LINK + f"/?start={self.username}"
