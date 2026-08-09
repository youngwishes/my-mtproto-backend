from __future__ import annotations

import json
from decimal import Decimal
from uuid import uuid4

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core import ActiveQuerySet, BaseDjangoModel
from apps.payments.enums import (
    CryptoPaymentIntentStatusEnum,
    PaymentKindEnum,
    PaymentMethodCodeEnum,
    PaymentProviderEnum,
    PlategaPaymentIntentStatusEnum,
    ProductCodeEnum,
)


class ProductQuerySet(ActiveQuerySet):
    def create_test_product(self) -> "Product":
        return self.create(
            code=ProductCodeEnum.MTPROTO_30D,
            title="MTPRoto Proxy Key",
            price=99 * 100,
            stars_price=99,
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
    code = models.CharField("код", max_length=32, unique=True)
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


class PaymentMethod(BaseDjangoModel):
    code = models.CharField(
        "код",
        max_length=32,
        unique=True,
        choices=PaymentMethodCodeEnum.choices(),
    )
    commission_percent = models.DecimalField(
        "комиссия, %",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=(
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("999.99")),
        ),
    )

    class Meta:
        verbose_name = "Способ оплаты"
        verbose_name_plural = "Способы оплаты"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    commission_percent__gte=Decimal("0.00"),
                    commission_percent__lte=Decimal("999.99"),
                ),
                name="payment_method_commission_percent_range",
            ),
        ]


class Payment(BaseDjangoModel):
    Kind = PaymentKindEnum

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
    kind = models.CharField(
        "тип платежа",
        max_length=32,
        choices=PaymentKindEnum.choices(),
        default=PaymentKindEnum.SUBSCRIPTION,
    )

    class Meta:
        verbose_name = "платеж"
        verbose_name_plural = "платежи"
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "charge_id", "kind"),
                condition=models.Q(kind=PaymentKindEnum.GIFT_CERTIFICATE),
                name="uniq_gift_certificate_payment_identity",
            ),
            models.UniqueConstraint(
                fields=("provider", "charge_id", "kind"),
                condition=models.Q(kind=PaymentKindEnum.VPN_SUBSCRIPTION),
                name="uniq_vpn_subscription_payment_identity",
            ),
            models.UniqueConstraint(
                fields=("provider", "charge_id", "kind"),
                condition=models.Q(provider=PaymentProviderEnum.CRYPTO_PAY),
                name="uniq_crypto_payment_identity",
            ),
        ]


class CryptoPaymentIntent(BaseDjangoModel):
    """Локальная покупка через Crypto Pay до и после выдачи результата."""

    public_id = models.UUIDField(
        "публичный UUID", default=uuid4, unique=True, editable=False
    )
    initiator = models.ForeignKey(
        "users.SystemUser",
        on_delete=models.PROTECT,
        related_name="crypto_payment_intents",
        verbose_name="инициатор",
    )
    purchase_kind = models.CharField(
        "тип покупки", max_length=32, choices=PaymentKindEnum.choices()
    )
    product_code = models.CharField("код продукта", max_length=32)
    rub_amount = models.DecimalField(
        "сумма в рублях", max_digits=10, decimal_places=2
    )
    status = models.CharField(
        "статус",
        max_length=32,
        choices=CryptoPaymentIntentStatusEnum.choices(),
        default=CryptoPaymentIntentStatusEnum.CREATING,
    )
    provider_invoice_id = models.PositiveBigIntegerField(
        "ID счёта Crypto Pay", null=True, blank=True, unique=True
    )
    provider_invoice_url = models.URLField(
        "URL счёта Crypto Pay", max_length=512, blank=True
    )
    provider_created_at = models.DateTimeField(
        "создан у провайдера", null=True, blank=True
    )
    provider_expires_at = models.DateTimeField(
        "истекает у провайдера", null=True, blank=True
    )
    paid_at = models.DateTimeField("оплачен", null=True, blank=True)
    fulfillment_attempted_at = models.DateTimeField(
        "попытка выдачи результата", null=True, blank=True
    )
    fulfilled_at = models.DateTimeField("результат выдан", null=True, blank=True)
    notification_sent_at = models.DateTimeField(
        "уведомление отправлено", null=True, blank=True
    )
    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="crypto_intent",
        verbose_name="платёж",
    )
    last_error_code = models.CharField(
        "код последней ошибки", max_length=64, blank=True
    )

    class Meta:
        verbose_name = "Платёж Crypto Pay"
        verbose_name_plural = "Платежи Crypto Pay"
        constraints = [
            models.UniqueConstraint(
                fields=("initiator", "purchase_kind"),
                condition=models.Q(
                    status__in=(
                        CryptoPaymentIntentStatusEnum.CREATING,
                        CryptoPaymentIntentStatusEnum.ACTIVE,
                    )
                ),
                name="uniq_active_crypto_intent_per_user_kind",
            ),
        ]


class PlategaPaymentIntent(BaseDjangoModel):
    """Локальная покупка через Platega SBP до и после выдачи результата."""

    public_id = models.UUIDField(
        "публичный UUID", default=uuid4, unique=True, editable=False
    )
    initiator = models.ForeignKey(
        "users.SystemUser",
        on_delete=models.PROTECT,
        related_name="platega_payment_intents",
        verbose_name="инициатор",
    )
    purchase_kind = models.CharField(
        "тип покупки", max_length=32, choices=PaymentKindEnum.choices()
    )
    product_code = models.CharField("код продукта", max_length=32)
    rub_amount = models.DecimalField(
        "сумма в рублях", max_digits=10, decimal_places=2
    )
    currency = models.CharField("валюта", max_length=3, default="RUB")
    payment_method = models.PositiveSmallIntegerField("способ оплаты", default=2)
    status = models.CharField(
        "статус",
        max_length=32,
        choices=PlategaPaymentIntentStatusEnum.choices(),
        default=PlategaPaymentIntentStatusEnum.CREATING,
    )
    provider_transaction_id = models.UUIDField(
        "ID транзакции Platega", null=True, blank=True, unique=True
    )
    provider_payment_url = models.URLField(
        "URL оплаты Platega", max_length=512, blank=True
    )
    provider_expires_at = models.DateTimeField(
        "истекает у провайдера", null=True, blank=True
    )
    fulfillment_attempted_at = models.DateTimeField(
        "попытка выдачи результата", null=True, blank=True
    )
    fulfilled_at = models.DateTimeField("результат выдан", null=True, blank=True)
    notification_queued_at = models.DateTimeField(
        "уведомление поставлено в очередь", null=True, blank=True
    )
    notification_sent_at = models.DateTimeField(
        "уведомление отправлено", null=True, blank=True
    )
    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="platega_intent",
        verbose_name="платёж",
    )
    last_error_code = models.CharField(
        "код последней ошибки", max_length=64, blank=True
    )

    class Meta:
        verbose_name = "Платёж Platega"
        verbose_name_plural = "Платежи Platega"
        constraints = [
            models.UniqueConstraint(
                fields=("initiator", "purchase_kind"),
                condition=models.Q(
                    status__in=(
                        PlategaPaymentIntentStatusEnum.CREATING,
                        PlategaPaymentIntentStatusEnum.ACTIVE,
                    )
                ),
                name="uniq_active_platega_intent_per_user_kind",
            ),
        ]


class GiftCertificate(BaseDjangoModel):
    class Status(models.TextChoices):
        CREATED = "created", "Создан"
        ACTIVATED = "activated", "Активирован"
        EXPIRED = "expired", "Истёк"

    code = models.CharField("код", max_length=13, unique=True)
    buyer = models.ForeignKey(
        "users.SystemUser",
        on_delete=models.CASCADE,
        related_name="gift_certificates_bought",
        verbose_name="покупатель",
    )
    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.CASCADE,
        related_name="gift_certificate",
        verbose_name="платёж",
    )
    expires_at = models.DateTimeField("действует до")
    activated_by = models.ForeignKey(
        "users.SystemUser",
        on_delete=models.SET_NULL,
        related_name="gift_certificates_activated",
        verbose_name="активировал",
        null=True,
        blank=True,
    )
    activated_at = models.DateTimeField("дата активации", null=True, blank=True)
    status = models.CharField(
        "статус",
        max_length=16,
        choices=Status.choices,
        default=Status.CREATED,
    )

    class Meta:
        verbose_name = "подарочный сертификат"
        verbose_name_plural = "подарочные сертификаты"
