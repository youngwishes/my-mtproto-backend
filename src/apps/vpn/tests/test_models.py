from __future__ import annotations

from django.db import IntegrityError
from django.test import TestCase

from apps.users.tests.factories import SystemUserFactory
from apps.vpn.models import VPNSubscription
from apps.vpn.tests.factories import VPNSubscriptionFactory


class TestVPNSubscriptionModel(TestCase):
    def test_user_can_have_only_one_subscription(self) -> None:
        user = SystemUserFactory()
        VPNSubscriptionFactory(user=user)

        with self.assertRaises(IntegrityError):
            VPNSubscriptionFactory(user=user)

    def test_credentials_are_created_once_and_remain_stable(self) -> None:
        subscription = VPNSubscriptionFactory()
        credentials = (
            subscription.token,
            subscription.vless_uuid,
            subscription.hysteria_secret,
        )

        subscription.save()
        subscription.refresh_from_db()

        self.assertTrue(all(credentials))
        self.assertEqual(
            (subscription.token, subscription.vless_uuid, subscription.hysteria_secret),
            credentials,
        )

    def test_last_reissued_at_is_nullable_and_blank_by_default(self) -> None:
        """Catches a cooldown field that requires a value for existing subscriptions."""
        field = VPNSubscription._meta.get_field("last_reissued_at")

        self.assertTrue(field.null)
        self.assertTrue(field.blank)
        self.assertIsNone(VPNSubscriptionFactory().last_reissued_at)
