import factory
from uuid import uuid4
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import Hosting, MTPRotoKey, VDSInstance


class HostingFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"hosting-{n}")
    link = factory.Sequence(lambda n: f"https://hosting-{n}.example.com")

    class Meta:
        model = Hosting


class VDSInstanceFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"vds-server-{n}")
    number = factory.Sequence(lambda n: n + 2)
    ip_address = factory.Sequence(lambda n: f"192.168.1.{n + 1}")
    internal_ip_address = factory.Sequence(lambda n: f"192.168.2.{n + 1}")
    is_keys_available = True
    port = 8000
    location = factory.Sequence(lambda n: f"🌍 Server {n}")
    hosting = factory.SubFactory(HostingFactory)

    class Meta:
        model = VDSInstance

class MTPRotoKeyFactory(factory.django.DjangoModelFactory):
    token = factory.LazyFunction(function=uuid4)
    user = factory.SubFactory(SystemUserFactory)
    expired_date = factory.LazyFunction(timezone.now)
    is_active = True
    was_deleted = False

    class Meta:
        model = MTPRotoKey
