from django.db import models
from django.db.models import Count

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
    port = models.SmallIntegerField("порт", default=8000)

    objects = VDSQuerySet.as_manager()

    @property
    def url(self) -> str:
        return f"http://{self.ip_address}:{self.port}"

    class Meta:
        verbose_name = "VDS сервер"
        verbose_name_plural = "VDS серверы"


class MTPRotoKey(BaseDjangoModel):
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

    def get_proxy_link(self) -> str:
        secret = self.get_secret_token()
        return f"tg://proxy?server={self.vds.ip_address}&port=443&secret={secret}"

    def get_secret_token(self) -> str:
        domain_hex = self.tls_domain.encode("utf-8").hex()
        return f"ee{self.token}{domain_hex}"

    class Meta:
        verbose_name = "MTPRoto ключ"
        verbose_name_plural = "MTPRoto ключи"
