from __future__ import annotations

import json
import secrets
from datetime import datetime
from typing import ClassVar
from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core import ActiveQuerySet, BaseDjangoModel
from apps.payments.enums import (
    PaymentIntentStatusEnum,
    PaymentKindEnum,
    PaymentProviderEnum,
    PaymentReceiptStatusEnum,
    ProductCodeEnum,
)


def generate_invoice_payload() -> str:
    """Return an unpredictable payment payload with 256 bits of entropy."""
    return secrets.token_hex(32)


validate_invoice_payload = RegexValidator(
    regex=r"\A[0-9a-f]{64}\Z",
    message="Payload должен быть 64-символьным lowercase hex token.",
)


class ProtectedWriteQuerySet(ActiveQuerySet):
    """Block generic ORM mutation of fields owned by a domain state machine."""

    protected_write_fields: ClassVar[frozenset[str]] = frozenset()

    def _validate_write_fields(self, *, fields: object) -> None:
        field_names = set()
        for field in fields:
            field_name = field if isinstance(field, str) else field.name
            if field_name not in self.protected_write_fields:
                field_name = field_name.removesuffix("_id")
            field_names.add(field_name)
        blocked = field_names & self.protected_write_fields
        if blocked:
            raise ValidationError(
                {field: "Используйте безопасный domain write API." for field in blocked}
            )

    def update(self, **kwargs: object) -> int:
        self._validate_write_fields(fields=kwargs)
        return super().update(**kwargs)

    def bulk_update(
        self,
        objs: object,
        fields: object,
        batch_size: int | None = None,
    ) -> int:
        self._validate_write_fields(fields=fields)
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def _safe_update(self, **kwargs: object) -> int:
        return models.QuerySet.update(self, **kwargs)


class PaymentIntentQuerySet(ProtectedWriteQuerySet):
    protected_write_fields = frozenset(
        {
            "user",
            "product",
            "invoice_payload",
            "currency",
            "amount",
            "provider",
            "expires_at",
            "status",
        }
    )

    def transition_status(
        self,
        *,
        intent_id: int,
        from_status: PaymentIntentStatusEnum,
        to_status: PaymentIntentStatusEnum,
    ) -> bool:
        allowed = {
            PaymentIntentStatusEnum.CREATED: {
                PaymentIntentStatusEnum.APPROVED,
                PaymentIntentStatusEnum.EXPIRED,
                PaymentIntentStatusEnum.CANCELLED,
            },
            PaymentIntentStatusEnum.APPROVED: {PaymentIntentStatusEnum.PAID},
        }
        if to_status not in allowed.get(from_status, set()):
            raise ValidationError({"status": "Недопустимый переход статуса."})
        return bool(
            self.filter(pk=intent_id, status=from_status)._safe_update(
                status=to_status,
                updated_at=timezone.now(),
            )
        )


class PaymentReceiptQuerySet(ProtectedWriteQuerySet):
    protected_write_fields = frozenset(
        {
            "intent",
            "user",
            "product",
            "provider",
            "charge_id",
            "currency",
            "amount",
            "accepted_at",
            "applied_at",
            "ready_at",
            "status",
            "attempt_count",
            "next_attempt_at",
            "processing_started_at",
            "lease_id",
            "last_error_code",
            "payment",
        }
    )

    def claim_for_processing(
        self,
        *,
        receipt_id: int,
        lease_id: UUID,
        started_at: datetime,
    ) -> bool:
        claimable = Q(status=PaymentReceiptStatusEnum.RECEIVED) | Q(
            status=PaymentReceiptStatusEnum.RETRY,
            next_attempt_at__lte=started_at,
        )
        return bool(
            self.filter(pk=receipt_id)
            .filter(claimable)
            ._safe_update(
                status=PaymentReceiptStatusEnum.PROCESSING,
                lease_id=lease_id,
                processing_started_at=started_at,
                attempt_count=F("attempt_count") + 1,
                next_attempt_at=None,
                last_error_code="",
                updated_at=timezone.now(),
            )
        )

    def mark_for_retry(
        self,
        *,
        receipt_id: int,
        lease_id: UUID,
        next_attempt_at: datetime,
        error_code: str,
    ) -> bool:
        return bool(
            self.filter(
                pk=receipt_id,
                status=PaymentReceiptStatusEnum.PROCESSING,
                lease_id=lease_id,
            )
            ._safe_update(
                status=PaymentReceiptStatusEnum.RETRY,
                lease_id=None,
                processing_started_at=None,
                next_attempt_at=next_attempt_at,
                last_error_code=error_code,
                updated_at=timezone.now(),
            )
        )

    def recover_stale_lease(
        self,
        *,
        receipt_id: int,
        stale_before: datetime,
        next_attempt_at: datetime,
    ) -> bool:
        return bool(
            self.filter(
                pk=receipt_id,
                status=PaymentReceiptStatusEnum.PROCESSING,
                lease_id__isnull=False,
                processing_started_at__lte=stale_before,
            )
            ._safe_update(
                status=PaymentReceiptStatusEnum.RETRY,
                lease_id=None,
                processing_started_at=None,
                next_attempt_at=next_attempt_at,
                last_error_code="stale_lease",
                updated_at=timezone.now(),
            )
        )

    def mark_applied(
        self,
        *,
        receipt_id: int,
        lease_id: UUID,
        payment: Payment,
        applied_at: datetime | None = None,
        ready_at: datetime | None = None,
    ) -> bool:
        effective_applied_at = applied_at or timezone.now()
        return bool(
            self.filter(
                pk=receipt_id,
                status=PaymentReceiptStatusEnum.PROCESSING,
                lease_id=lease_id,
                user_id=payment.user_id,
                product_id=payment.product_id,
                provider=payment.provider,
                charge_id=payment.charge_id,
            )
            ._safe_update(
                status=PaymentReceiptStatusEnum.APPLIED,
                payment=payment,
                applied_at=effective_applied_at,
                ready_at=ready_at,
                lease_id=None,
                processing_started_at=None,
                next_attempt_at=None,
                last_error_code="",
                updated_at=timezone.now(),
            )
        )


class ImmutableFieldsModel(models.Model):
    """Reject model saves that alter declared immutable persisted fields."""

    immutable_fields: ClassVar[tuple[str, ...]] = ()
    safe_write_fields: ClassVar[tuple[str, ...]] = ()

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk is not None and not self._state.adding:
            protected_fields = self.immutable_fields + self.safe_write_fields
            persisted = (
                type(self)
                .objects.filter(pk=self.pk)
                .values(*protected_fields)
                .first()
            )
            if persisted is not None:
                immutable_changed = [
                    field
                    for field in self.immutable_fields
                    if persisted[field] != getattr(self, field)
                ]
                safe_write_changed = [
                    field
                    for field in self.safe_write_fields
                    if persisted[field] != getattr(self, field)
                ]
                if immutable_changed:
                    raise ValidationError(
                        {
                            field: "Поле нельзя изменить после создания."
                            for field in immutable_changed
                        }
                    )
                if safe_write_changed:
                    raise ValidationError(
                        {
                            field: "Используйте безопасный domain write API."
                            for field in safe_write_changed
                        }
                    )
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


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
    code = models.CharField(
        "стабильный код",
        max_length=32,
        choices=ProductCodeEnum.choices(),
        null=True,
        blank=True,
    )
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
        constraints = [
            models.UniqueConstraint(
                fields=("code",),
                condition=models.Q(code__isnull=False) & ~models.Q(code=""),
                name="uniq_non_empty_product_code",
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
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="товар",
        null=True,
        blank=True,
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
                fields=("provider", "charge_id"),
                condition=~models.Q(charge_id=""),
                name="uniq_non_empty_payment_identity",
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


class PaymentIntent(ImmutableFieldsModel, BaseDjangoModel):
    """Durable invoice parameters whose commercial identity never changes."""

    immutable_fields = (
        "user_id",
        "product_id",
        "invoice_payload",
        "currency",
        "amount",
        "provider",
        "expires_at",
    )
    safe_write_fields = ("status",)

    user = models.ForeignKey(
        "users.SystemUser",
        on_delete=models.CASCADE,
        related_name="payment_intents",
        verbose_name="пользователь",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="payment_intents",
        verbose_name="товар",
    )
    invoice_payload = models.CharField(
        "invoice payload",
        max_length=64,
        unique=True,
        default=generate_invoice_payload,
        validators=(validate_invoice_payload,),
    )
    currency = models.CharField("валюта", max_length=8)
    amount = models.PositiveBigIntegerField(
        "сумма в минимальных единицах валюты",
        validators=(MinValueValidator(1),),
    )
    provider = models.CharField(
        "провайдер",
        max_length=16,
        choices=PaymentProviderEnum.choices(),
    )
    expires_at = models.DateTimeField("действует до")
    status = models.CharField(
        "статус",
        max_length=32,
        choices=PaymentIntentStatusEnum.choices(),
        default=PaymentIntentStatusEnum.CREATED,
    )

    objects = PaymentIntentQuerySet.as_manager()

    @property
    def is_expired(self) -> bool:
        return (
            self.status == PaymentIntentStatusEnum.CREATED
            and self.expires_at <= timezone.now()
        )

    @property
    def accepts_successful_payment(self) -> bool:
        return self.status == PaymentIntentStatusEnum.APPROVED

    def transition_to(self, *, status: PaymentIntentStatusEnum) -> None:
        transitioned = PaymentIntent.objects.transition_status(
            intent_id=self.pk,
            from_status=PaymentIntentStatusEnum(self.status),
            to_status=status,
        )
        if not transitioned:
            raise ValidationError({"status": "Статус уже изменён конкурентно."})
        self.refresh_from_db()

    class Meta:
        verbose_name = "намерение платежа"
        verbose_name_plural = "намерения платежей"
        constraints = [
            models.CheckConstraint(
                condition=Q(invoice_payload__regex=r"\A[0-9a-f]{64}\Z"),
                name="valid_payment_intent_payload",
            ),
        ]


class PaymentReceipt(ImmutableFieldsModel, BaseDjangoModel):
    """Durable provider receipt with recoverable lease and retry state."""

    immutable_fields = (
        "intent_id",
        "user_id",
        "product_id",
        "provider",
        "charge_id",
        "currency",
        "amount",
        "accepted_at",
        "applied_at",
        "ready_at",
    )
    safe_write_fields = (
        "status",
        "attempt_count",
        "next_attempt_at",
        "processing_started_at",
        "lease_id",
        "last_error_code",
        "payment_id",
    )

    intent = models.OneToOneField(
        PaymentIntent,
        on_delete=models.PROTECT,
        related_name="receipt",
        verbose_name="намерение платежа",
    )
    user = models.ForeignKey(
        "users.SystemUser",
        on_delete=models.CASCADE,
        related_name="payment_receipts",
        verbose_name="пользователь",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="payment_receipts",
        verbose_name="товар",
    )
    provider = models.CharField(
        "провайдер",
        max_length=16,
        choices=PaymentProviderEnum.choices(),
    )
    charge_id = models.CharField("ID платежа у провайдера")
    currency = models.CharField("валюта", max_length=8)
    amount = models.PositiveBigIntegerField(
        "сумма в минимальных единицах валюты",
        validators=(MinValueValidator(1),),
    )
    accepted_at = models.DateTimeField("принят", auto_now_add=True)
    applied_at = models.DateTimeField("применён", null=True, blank=True)
    ready_at = models.DateTimeField("VPN-доступ готов", null=True, blank=True)
    status = models.CharField(
        "статус",
        max_length=16,
        choices=PaymentReceiptStatusEnum.choices(),
        default=PaymentReceiptStatusEnum.RECEIVED,
    )
    attempt_count = models.PositiveIntegerField("число попыток", default=0)
    next_attempt_at = models.DateTimeField(
        "следующая попытка",
        null=True,
        blank=True,
    )
    processing_started_at = models.DateTimeField(
        "начало обработки",
        null=True,
        blank=True,
    )
    lease_id = models.UUIDField("ID аренды", null=True, blank=True)
    last_error_code = models.CharField(
        "безопасный код последней ошибки",
        max_length=64,
        blank=True,
    )
    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        related_name="receipt",
        verbose_name="применённый платёж",
        null=True,
        blank=True,
    )

    objects = PaymentReceiptQuerySet.as_manager()

    @property
    def is_ready_for_processing(self) -> bool:
        if self.status == PaymentReceiptStatusEnum.RECEIVED:
            return True
        return (
            self.status == PaymentReceiptStatusEnum.RETRY
            and (self.next_attempt_at is None or self.next_attempt_at <= timezone.now())
        )

    def has_stale_lease(self, *, stale_before: datetime) -> bool:
        return (
            self.status == PaymentReceiptStatusEnum.PROCESSING
            and self.processing_started_at is not None
            and self.processing_started_at <= stale_before
        )

    class Meta:
        verbose_name = "квитанция платежа"
        verbose_name_plural = "квитанции платежей"
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "charge_id"),
                name="uniq_payment_receipt_identity",
            ),
            models.CheckConstraint(
                condition=~models.Q(charge_id=""),
                name="non_empty_payment_receipt_charge_id",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=PaymentReceiptStatusEnum.PROCESSING,
                        lease_id__isnull=False,
                        processing_started_at__isnull=False,
                    )
                    | Q(
                        ~Q(status=PaymentReceiptStatusEnum.PROCESSING),
                        lease_id__isnull=True,
                        processing_started_at__isnull=True,
                    )
                ),
                name="coherent_payment_receipt_lease",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=PaymentReceiptStatusEnum.RETRY,
                        next_attempt_at__isnull=False,
                    )
                    | Q(
                        ~Q(status=PaymentReceiptStatusEnum.RETRY),
                        next_attempt_at__isnull=True,
                    )
                ),
                name="coherent_payment_receipt_retry",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=PaymentReceiptStatusEnum.APPLIED,
                        payment__isnull=False,
                    )
                    | Q(
                        ~Q(status=PaymentReceiptStatusEnum.APPLIED),
                        payment__isnull=True,
                    )
                ),
                name="coherent_payment_receipt_applied",
            ),
            models.CheckConstraint(
                condition=(
                    Q(ready_at__isnull=True)
                    | Q(applied_at__isnull=True)
                    | Q(ready_at__gte=F("applied_at"))
                ),
                name="payment_receipt_ready_not_before_applied",
            ),
        ]
