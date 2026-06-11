from __future__ import annotations

import json

from django.db import models

from apps.core import ActiveQuerySet, BaseDjangoModel
from apps.payments.enums import PaymentProviderEnum


class ProductQuerySet(ActiveQuerySet):
    def create_test_product(self) -> "Product":
        return self.create(
            title="MTPRoto Proxy Key",
            price=99 * 100,
            stars_price=80,
            description="Позволяет ускорить работу мессенджера Telegram. Работает сразу на 3-ех устройствах.",
            provider_data=json.dumps(
                {
                    "customer": {},
                    "items": [
                        {
                            "description": "Оплата подписки на телеграмм-канал на один месяц.",
                            "quantity": "1.00",
                            "amount": {
                                "value": 99,
                                "currency": "RUB",
                            },
                            "vat_code": 4,
                            "payment_mode": "full_payment",
                        }
                    ],
                }
            ),
        )


class Product(BaseDjangoModel):
    title = models.CharField("название")
    description = models.TextField("описание")
    currency = models.CharField("валюта", default="RUB")
    provider_data = models.TextField("provider_data")
    send_email_to_provider = models.BooleanField(
        "отправить email продавцу", default=True
    )
    need_email = models.BooleanField("спрашивать почту", default=True)
    price = models.DecimalField("цена", max_digits=10, decimal_places=2)
    stars_price = models.PositiveIntegerField("цена в звёздах", default=80)

    objects = ProductQuerySet.as_manager()

    @property
    def provider_data_json(self) -> dict:
        return json.loads(self.provider_data)

    class Meta:
        verbose_name = "товар"
        verbose_name_plural = "товары"


class Payment(BaseDjangoModel):
    user = models.ForeignKey(
        "users.SystemUser",
        on_delete=models.CASCADE,
        related_name="kassa_payments",
        verbose_name="пользователь",
    )
    key = models.OneToOneField(
        "vds.MTPRotoKey",
        on_delete=models.SET_NULL,
        related_name="kassa_payment",
        verbose_name="ключ",
        null=True,
    )
    charge_id = models.CharField(
        "ID платежа у провайдера",
        blank=True,
    )
    provider = models.CharField(
        "провайдер",
        max_length=16,
        choices=PaymentProviderEnum.choices(),
        default=PaymentProviderEnum.YUKASSA,
    )

    class Meta:
        verbose_name = "платеж"
        verbose_name_plural = "платежи"
