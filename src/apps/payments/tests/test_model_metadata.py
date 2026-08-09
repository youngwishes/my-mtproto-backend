from __future__ import annotations

from django.test import SimpleTestCase

from apps.payments.models import (
    CryptoPaymentIntent,
    PaymentMethod,
    PlategaPaymentIntent,
)


class TestPaymentModelMetadata(SimpleTestCase):
    inherited_field_verbose_names = {
        "id": "ID",
        "is_active": "активность",
        "created_at": "дата создания",
        "updated_at": "дата обновления",
    }
    model_verbose_names = (
        (PaymentMethod, ("Способ оплаты", "Способы оплаты")),
        (CryptoPaymentIntent, ("Платёж Crypto Pay", "Платежи Crypto Pay")),
        (PlategaPaymentIntent, ("Платёж Platega", "Платежи Platega")),
    )
    own_field_verbose_names = (
        (
            PaymentMethod,
            {
                "code": "код",
                "commission_percent": "комиссия, %",
                "is_priority": "приоритетный",
            },
        ),
        (
            CryptoPaymentIntent,
            {
                "public_id": "публичный UUID",
                "initiator": "инициатор",
                "purchase_kind": "тип покупки",
                "product_code": "код продукта",
                "rub_amount": "сумма в рублях",
                "status": "статус",
                "provider_invoice_id": "ID счёта Crypto Pay",
                "provider_invoice_url": "URL счёта Crypto Pay",
                "provider_created_at": "создан у провайдера",
                "provider_expires_at": "истекает у провайдера",
                "paid_at": "оплачен",
                "fulfillment_attempted_at": "попытка выдачи результата",
                "fulfilled_at": "результат выдан",
                "notification_sent_at": "уведомление отправлено",
                "payment": "платёж",
                "last_error_code": "код последней ошибки",
            },
        ),
        (
            PlategaPaymentIntent,
            {
                "public_id": "публичный UUID",
                "initiator": "инициатор",
                "purchase_kind": "тип покупки",
                "product_code": "код продукта",
                "rub_amount": "сумма в рублях",
                "currency": "валюта",
                "payment_method": "способ оплаты",
                "status": "статус",
                "provider_transaction_id": "ID транзакции Platega",
                "provider_payment_url": "URL оплаты Platega",
                "provider_expires_at": "истекает у провайдера",
                "fulfillment_attempted_at": "попытка выдачи результата",
                "fulfilled_at": "результат выдан",
                "notification_queued_at": "уведомление поставлено в очередь",
                "notification_sent_at": "уведомление отправлено",
                "payment": "платёж",
                "last_error_code": "код последней ошибки",
            },
        ),
    )

    def test_models_have_approved_verbose_names(self) -> None:
        for model, expected_model_names in self.model_verbose_names:
            with self.subTest(model=model.__name__):
                self.assertEqual(
                    (str(model._meta.verbose_name), str(model._meta.verbose_name_plural)),
                    expected_model_names,
                )

    def test_own_fields_have_approved_verbose_names(self) -> None:
        for model, expected_own_fields in self.own_field_verbose_names:
            with self.subTest(model=model.__name__):
                actual_own_fields = {
                    field.name: str(field.verbose_name)
                    for field in model._meta.fields
                    if field.name not in self.inherited_field_verbose_names
                }
                self.assertEqual(actual_own_fields, expected_own_fields)

    def test_inherited_fields_keep_existing_verbose_names(self) -> None:
        for model in (PaymentMethod, CryptoPaymentIntent, PlategaPaymentIntent):
            for field_name, expected_verbose_name in (
                self.inherited_field_verbose_names.items()
            ):
                with self.subTest(model=model.__name__, field=field_name):
                    field = model._meta.get_field(field_name)

                    self.assertEqual(str(field.verbose_name), expected_verbose_name)
