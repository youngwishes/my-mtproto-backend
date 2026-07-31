from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

from django.test import TestCase
from django.utils import timezone

from apps.vpn.selectors import get_active_vpn_instances, get_expired_active_vpn_subscriptions
from apps.vpn.services import ExpireVPNSubscriptionsService
from apps.vpn.tests.factories import VPNInstanceFactory, VPNSubscriptionFactory


class TestExpireVPNSubscriptionsService(TestCase):
    def test_deactivates_expired_subscriptions_before_enqueueing_deletes_to_active_nodes(self) -> None:
        now = timezone.now()
        expired = VPNSubscriptionFactory(expired_at=now - timedelta(seconds=1))
        future = VPNSubscriptionFactory(expired_at=now + timedelta(days=1))
        inactive = VPNSubscriptionFactory(
            is_active=False,
            expired_at=now - timedelta(seconds=1),
        )
        active_instance = VPNInstanceFactory(is_active=True)
        VPNInstanceFactory(is_active=False)
        enqueue_delivery = Mock()

        service = ExpireVPNSubscriptionsService(
            get_expired_subscriptions=get_expired_active_vpn_subscriptions,
            get_active_instances=get_active_vpn_instances,
            enqueue_delivery=enqueue_delivery,
        )

        with self.captureOnCommitCallbacks(execute=True):
            deactivated_count = service(now=now)

        expired.refresh_from_db()
        future.refresh_from_db()
        inactive.refresh_from_db()
        self.assertEqual(deactivated_count, 1)
        self.assertFalse(expired.is_active)
        self.assertTrue(future.is_active)
        self.assertFalse(inactive.is_active)
        enqueue_delivery.assert_called_once_with(
            subscription_id=expired.pk,
            instance_id=active_instance.pk,
            operation="delete",
        )
