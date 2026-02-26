from uuid import uuid4
from datetime import datetime
import factory

from apps.tribute.models import TributeDigitalPayment


class TributeDigitalPaymentFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(function=lambda n: f"name{n}")
    product_id = factory.Sequence(function=lambda n: n + 1)
    product_name = factory.Sequence(function=lambda n: f"product_name{n}")
    amount = factory.Sequence(function=lambda n: n + 1)
    currency = "RUB"
    telegram_user_id = factory.LazyFunction(function=uuid4)
    is_success = False
    purchase_created_at = factory.LazyFunction(function=datetime.now)

    class Meta:
        model = TributeDigitalPayment
