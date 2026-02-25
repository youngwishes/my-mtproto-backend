import factory

from apps.vds.models import VDSInstance


class VDSInstanceFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"vds-server-{n}")
    number = factory.Sequence(lambda n: n + 1)
    ip_address = factory.Sequence(lambda n: f"192.168.1.{n + 1}")
    port = 8000

    class Meta:
        model = VDSInstance
