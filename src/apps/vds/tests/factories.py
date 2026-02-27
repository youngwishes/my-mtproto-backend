import factory
from uuid import uuid4
from apps.tribute.tests.factories import TributeDigitalPaymentFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import VDSInstance, MTPRotoKey


class VDSInstanceFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"vds-server-{n}")
    number = factory.Sequence(lambda n: n + 2)
    ip_address = factory.Sequence(lambda n: f"192.168.1.{n + 1}")
    port = 8000

    class Meta:
        model = VDSInstance



class MTPRotoKeyFactory(factory.django.DjangoModelFactory):
    token = factory.LazyFunction(function=uuid4)
    vds = factory.SubFactory(VDSInstanceFactory)
    user = factory.SubFactory(SystemUserFactory)
    payment = factory.SubFactory(TributeDigitalPaymentFactory)
    tls_domain = "petrovich.ru"
    is_active = True
    was_deleted = False

    class Meta:
        model = MTPRotoKey
