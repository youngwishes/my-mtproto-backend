import factory

from apps.payments.enums import PaymentProviderEnum
from apps.payments.models import Payment, Product


class ProductFactory(factory.django.DjangoModelFactory):
    title = factory.Sequence(function=lambda n: f"title{n}")
    provider_data = factory.Sequence(function=lambda n: '{"key": "value"}')
    description = factory.Sequence(function=lambda n: f"description_{n}")
    price = 79
    stars_price = 60
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
