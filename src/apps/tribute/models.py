from django.db import models

from apps.core import BaseDjangoModel


class TributeDigitalPayment(BaseDjangoModel):
    name = models.CharField("название события")
    product_id = models.IntegerField("ID товара")
    product_name = models.CharField("название товара")
    amount = models.FloatField("стоимость")
    currency = models.CharField("валюта")
    telegram_user_id = models.CharField("ID пользователя в Telegram")
    purchase_created_at = models.DateTimeField("дата оплаты на Tribute")
    is_success = models.BooleanField("ссылка отправлена пользователю", default=False)

    class Meta:
        verbose_name = "платеж на Tribute"
        verbose_name_plural = "платежи на Tribute"
