import factory
from datetime import timedelta

from django.utils import timezone

from apps.payments.enums import PaymentProviderEnum, ProductCodeEnum
from apps.payments.models import GiftCertificate, Payment, Product


class ProductFactory(factory.django.DjangoModelFactory):
    code = factory.Sequence(lambda n: f"product_{n}")
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
