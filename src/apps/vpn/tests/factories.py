from __future__ import annotations

from datetime import timedelta

import factory
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vpn.models import VPNInstance, VPNSubscription


class VPNSubscriptionFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(SystemUserFactory)
    expired_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))

    class Meta:
        model = VPNSubscription


class VPNInstanceFactory(factory.django.DjangoModelFactory):
    number = factory.Sequence(lambda number: number + 1)
    name = factory.Sequence(lambda number: f"vpn-{number}")
    location = factory.Sequence(lambda number: f"Location {number}")
    management_url = factory.Sequence(
        lambda number: f"https://management-{number}.example.com",
    )
    public_host = factory.Sequence(lambda number: f"vpn-{number}.example.com")
    vless_port = 443
    reality_sni = "www.example.com"
    reality_public_key = "public-key"
    reality_short_id = "short-id"
    hysteria_port = 443
    hysteria_sni = "www.example.com"
    hysteria_obfs = "obfs-password"

    class Meta:
        model = VPNInstance
