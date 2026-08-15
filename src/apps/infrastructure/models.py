from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.core import BaseDjangoModel
from apps.infrastructure.enums import ProjectServerCurrency


class ProjectServer(BaseDjangoModel):
    ipv4 = models.GenericIPAddressField(
        "IPv4-адрес",
        protocol="IPv4",
        unique=True,
    )
    hosting = models.ForeignKey(
        "vds.Hosting",
        on_delete=models.PROTECT,
        related_name="project_servers",
        verbose_name="хостинг",
    )
    price = models.DecimalField(
        "стоимость в месяц",
        max_digits=10,
        decimal_places=2,
        validators=(MinValueValidator(Decimal("0.01")),),
    )
    currency = models.CharField(
        "валюта",
        max_length=4,
        choices=ProjectServerCurrency.choices,
    )
    next_payment_date = models.DateField("дата следующего платежа")
    description = models.CharField("назначение", max_length=255)

    def __str__(self) -> str:
        return self.ipv4

    class Meta:
        verbose_name = "Проектный сервер"
        verbose_name_plural = "Проектные серверы"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gt=Decimal("0.00")),
                name="project_server_price_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(currency__in=ProjectServerCurrency.values),
                name="project_server_currency_valid",
            ),
        ]
