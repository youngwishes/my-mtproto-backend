from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vpn.selectors import (
    get_active_vpn_instances,
    get_active_vpn_subscription,
)
from apps.vpn.tests.factories import VPNInstanceFactory, VPNSubscriptionFactory


class TestGetActiveVPNInstances(TestCase):
    def test_returns_only_active_instances_sorted_by_number_then_id(self) -> None:
        later = VPNInstanceFactory(number=20)
        first_with_same_number = VPNInstanceFactory(number=10)
        second_with_same_number = VPNInstanceFactory(number=10)
        VPNInstanceFactory(number=1, is_active=False)

        self.assertEqual(
            list(get_active_vpn_instances()),
            [first_with_same_number, second_with_same_number, later],
        )


class TestGetActiveVPNSubscription(TestCase):
    def test_returns_only_active_and_unexpired_subscription_for_user(self) -> None:
        user = SystemUserFactory()
        active = VPNSubscriptionFactory(
            user=user,
            expired_at=timezone.now() + timedelta(minutes=1),
        )
        expired_user = SystemUserFactory()
        VPNSubscriptionFactory(
            user=expired_user,
            expired_at=timezone.now() - timedelta(minutes=1),
        )
        inactive_user = SystemUserFactory()
        VPNSubscriptionFactory(user=inactive_user, is_active=False)

        self.assertEqual(get_active_vpn_subscription(user=user), active)
        self.assertIsNone(get_active_vpn_subscription(user=expired_user))
        self.assertIsNone(get_active_vpn_subscription(user=inactive_user))
