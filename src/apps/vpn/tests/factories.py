from __future__ import annotations

from datetime import timedelta
import factory
from django.utils import timezone

from apps.payments.tests.factories import PaymentFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vpn.enums import VPNAccessState, VPNApplyStatus, VPNNodeHealthState
from apps.vpn.models import VPNAccess, VPNAccessNodeApply, VPNNode, VPNPurchase


class VPNAccessFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(SystemUserFactory)
    expired_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
    state = VPNAccessState.PREPARING

    class Meta:
        model = VPNAccess


class VPNPurchaseFactory(factory.django.DjangoModelFactory):
    payment = factory.SubFactory(PaymentFactory)
    access = factory.SubFactory(VPNAccessFactory)
    expired_at_after = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=30)
    )

    class Meta:
        model = VPNPurchase


class VPNNodeFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"vpn-node-{n}")
    number = factory.Sequence(lambda n: n + 1)
    location = factory.Sequence(lambda n: f"Location {n}")
    host = factory.Sequence(lambda n: f"vpn-{n}.example.com")
    port = 443
    agent_base_url = factory.Sequence(lambda n: f"https://agent-{n}.example.com")
    agent_secret_key = factory.Sequence(lambda n: f"VPN_NODE_{n}_AGENT_TOKEN")
    agent_contract_version = "v1"
    health_state = VPNNodeHealthState.NEW
    reality_public_key = "UEnA5W5Lk_7-ywBVKfM8kS4DFwQ6F6-y9vDSS2rQYF8"
    reality_short_id = "0123456789abcdef"
    reality_server_name = "www.example.com"

    class Meta:
        model = VPNNode


class VPNAccessNodeApplyFactory(factory.django.DjangoModelFactory):
    access = factory.SubFactory(VPNAccessFactory)
    node = factory.SubFactory(VPNNodeFactory)
    desired_revision = factory.LazyAttribute(lambda obj: obj.access.desired_revision)
    status = VPNApplyStatus.PENDING

    class Meta:
        model = VPNAccessNodeApply
