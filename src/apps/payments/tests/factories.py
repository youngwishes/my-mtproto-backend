from __future__ import annotations

import factory
from datetime import timedelta

from django.utils import timezone

from apps.payments.enums import PaymentIntentStatusEnum, PaymentProviderEnum
from apps.payments.models import (
    GiftCertificate,
    Payment,
    PaymentIntent,
    PaymentReceipt,
    Product,
)


class ProductFactory(factory.django.DjangoModelFactory):
    code = None
    title = factory.Sequence(function=lambda n: f"title{n}")
    provider_data = factory.Sequence(function=lambda n: '{"key": "value"}')
    description = factory.Sequence(function=lambda n: f"description_{n}")
    price = 99
    stars_price = 80
    currency = "RUB"

    class Meta:
        model = Product


class PaymentFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory("apps.users.tests.factories.SystemUserFactory")
    key = None
    product = None
    charge_id = factory.Sequence(lambda n: f"charge_{n}")
    provider = PaymentProviderEnum.YUKASSA

    class Meta:
        model = Payment


class GiftCertificateFactory(factory.django.DjangoModelFactory):
    code = factory.Sequence(lambda n: f"KEY-T{n:03d}-ABCD")
    buyer = factory.SubFactory("apps.users.tests.factories.SystemUserFactory")
    payment = factory.SubFactory(PaymentFactory)
    expires_at = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=365)
    )

    class Meta:
        model = GiftCertificate


class PaymentIntentFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory("apps.users.tests.factories.SystemUserFactory")
    product = factory.SubFactory(ProductFactory)
    currency = "RUB"
    amount = 9900
    provider = PaymentProviderEnum.YUKASSA
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=15))
    status = PaymentIntentStatusEnum.CREATED

    class Meta:
        model = PaymentIntent


class PaymentReceiptFactory(factory.django.DjangoModelFactory):
    intent = factory.SubFactory(PaymentIntentFactory)
    user = factory.SelfAttribute("intent.user")
    product = factory.SelfAttribute("intent.product")
    provider = factory.SelfAttribute("intent.provider")
    charge_id = factory.Sequence(lambda n: f"receipt_charge_{n}")
    currency = factory.SelfAttribute("intent.currency")
    amount = factory.SelfAttribute("intent.amount")

    class Meta:
        model = PaymentReceipt
