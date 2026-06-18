from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models.enums import IntegerChoices
from apps.core import BaseDjangoModel, ActiveQuerySet


class VDSInstance(BaseDjangoModel):
    name = models.CharField("название сервера")
    number = models.PositiveSmallIntegerField("порядковый номер", unique=True)
    ip_address = models.CharField("IP-адрес", unique=True)
    internal_ip_address = models.CharField("внутренний IP-адрес", blank=True)
    port = models.SmallIntegerField("порт", default=8000)
    is_keys_available = models.BooleanField("выпуск ключей доступен", default=True)
    is_healthy = models.BooleanField("сервер здоров", default=True)
    location = models.CharField("геолокация", default="", blank=True)

    objects = ActiveQuerySet.as_manager()

    @property
    def internal_url(self) -> str:
        return f"http://{self.internal_ip_address}:{self.port}"

    @property
    def external_url(self) -> str:
        return f"http://{self.ip_address}:{self.port}"

    def __str__(self) -> str:
        return self.internal_ip_address

    class Meta:
        verbose_name = "VDS сервер"
        verbose_name_plural = "VDS серверы"
        ordering = ["number"]


class MTPRotoKeyQuerySet(ActiveQuerySet):
    def expired_today(self) -> MTPRotoKeyQuerySet:
        from django.utils import timezone

        return self.filter(
            was_deleted=False,
            expired_date__date__lte=timezone.now().date()
        )


class MTPRotoKey(BaseDjangoModel):
    class FreePeriod(IntegerChoices):
        WEEK = 1
        TWO_WEEK = 2
        MONTH = 3

    token = models.CharField("токен", unique=True)
    user = models.ForeignKey(
        to="users.SystemUser",
        on_delete=models.CASCADE,
        verbose_name="владелец",
        related_name="keys",
    )
    was_deleted = models.BooleanField("удален", default=False)
    user_notified = models.BooleanField("уведомлен об истечении", default=False)
    expired_date = models.DateTimeField("истекает", blank=True, null=True)
    last_update = models.DateTimeField("последнее обновление", blank=True, null=True)
    objects = MTPRotoKeyQuerySet.as_manager()

    def __str__(self) -> str:
        return f"MTPRotoKey #{self.pk} — {self.user_id}"

    def get_secret_token(self) -> str:
        domain_hex = settings.TLS_DOMAIN.encode("utf-8").hex()
        return f"ee{self.token}{domain_hex}"

    def get_proxy_link(self, *, server_name: str) -> str:
        """Единственный генератор proxy-ссылки: секрет валиден на всём флоте,
        хост определяется именем конкретного сервера ({server_name}.beatvault.ru)."""
        secret = self.get_secret_token()
        return f"tg://proxy?server={server_name}.beatvault.ru&port=443&secret={secret}"

    class Meta:
        verbose_name = "MTPRoto ключ"
        verbose_name_plural = "MTPRoto ключи"
