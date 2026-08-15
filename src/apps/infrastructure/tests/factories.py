from __future__ import annotations

from datetime import date
from decimal import Decimal

import factory

from apps.infrastructure.enums import ProjectServerCurrency
from apps.infrastructure.models import ProjectServer
from apps.vds.tests.factories import HostingFactory


class ProjectServerFactory(factory.django.DjangoModelFactory):
    ipv4 = factory.Sequence(
        lambda number: f"10.200.{number // 254}.{number % 254 + 1}"
    )
    hosting = factory.SubFactory(HostingFactory)
    price = Decimal("10.00")
    currency = ProjectServerCurrency.USDT
    next_payment_date = factory.LazyFunction(date.today)
    description = factory.Sequence(lambda number: f"project server {number}")

    class Meta:
        model = ProjectServer
