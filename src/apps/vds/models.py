from django.db import models
from apps.core import BaseDjangoModel


class VDSInstance(BaseDjangoModel):
    name = models.CharField("название сервера", unique=True)
    number = models.PositiveSmallIntegerField("порядковый номер", unique=True)
    ip_address = models.CharField("IP-адрес", unique=True)
    port = models.SmallIntegerField("порт", default=8000)

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

    class Meta:
        verbose_name = "MTPRoto ключ"
        verbose_name_plural = "MTPRoto ключи"
