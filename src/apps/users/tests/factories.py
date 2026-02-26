import factory

from apps.users.models import SystemUser


class SystemUserFactory(factory.django.DjangoModelFactory):
    username = factory.Sequence(function=lambda n: f"user{n}")

    class Meta:
        model = SystemUser
