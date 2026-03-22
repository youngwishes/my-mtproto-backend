from django.db import models
from django.db.models import Count
from django.db.models.enums import IntegerChoices
from apps.core import BaseDjangoModel, ActiveQuerySet


class VDSQuerySet(ActiveQuerySet):
    def order_by_population(self):
        return (
            self.active()
            .annotate(keys_count_annotation=Count("keys"))
            .order_by("keys_count_annotation")
        )

    def get_least_populated(self):
        return self.order_by_population().first()


class VDSInstance(BaseDjangoModel):
    name = models.CharField("название сервера", unique=True)
    number = models.PositiveSmallIntegerField("порядковый номер", unique=True)
    ip_address = models.CharField("IP-адрес", unique=True)
    internal_ip_address = models.CharField("внутренний IP-адрес", blank=True)
    port = models.SmallIntegerField("порт", default=8000)
    user_limit = models.PositiveSmallIntegerField("лимит пользователей", default=200)

    objects = VDSQuerySet.as_manager()

    def is_available(self) -> bool:
        return self.keys.filter(is_active=True, was_deleted=False).count() < self.user_limit

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


class MTPRotoKeyQuerySet(ActiveQuerySet):
    def expired_today(self) -> "MTPRotoKeyQuerySet":
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
    vds = models.ForeignKey(
        to=VDSInstance,
        on_delete=models.CASCADE,
        verbose_name="VDS сервер",
        related_name="keys",
    )
    user = models.ForeignKey(
        to="users.SystemUser",
        on_delete=models.CASCADE,
        verbose_name="владелец",
        related_name="keys",
    )
    payment = models.OneToOneField(
        "tribute.TributeDigitalPayment",
        on_delete=models.CASCADE,
        verbose_name="оплата на Tribute",
        related_name="key",
        null=True,
        blank=True,
    )
    was_deleted = models.BooleanField("удален", default=False)
    tls_domain = models.CharField("домен ключа в telemt")
    node_number = models.CharField("номер ноды", blank=True)
    user_notified = models.BooleanField("уведомлен об истечении", default=False)
    expired_date = models.DateTimeField("истекает", blank=True, null=True)
    last_update = models.DateTimeField("последнее обновление", blank=True, null=True)
    objects = MTPRotoKeyQuerySet.as_manager()

    def __str__(self) -> str:
        return self.get_proxy_link()

    def get_proxy_link(self) -> str:
        secret = self.get_secret_token()
        return f"tg://proxy?server={self.node_number}.beatvault.ru&port=443&secret={secret}"

    def get_secret_token(self) -> str:
        domain_hex = self.tls_domain.encode("utf-8").hex()
        return f"ee{self.token}{domain_hex}"

    class Meta:
        verbose_name = "MTPRoto ключ"
        verbose_name_plural = "MTPRoto ключи"
