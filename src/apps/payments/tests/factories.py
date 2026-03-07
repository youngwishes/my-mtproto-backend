import factory

from apps.payments.models import Product


class ProductFactory(factory.django.DjangoModelFactory):
    title = factory.Sequence(function=lambda n: f"title{n}")
    provider_data = factory.Sequence(function=lambda n: '{"key": "value"}')
    description = factory.Sequence(function=lambda n: f"description_{n}")
    price = 69
    currency = "RUB"

    class Meta:
        model = Product
