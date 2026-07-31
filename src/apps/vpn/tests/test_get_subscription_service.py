from __future__ import annotations

from django.test import TestCase

from apps.vpn.services import get_subscription_service


class TestGetSubscriptionService(TestCase):
    def test_unknown_token_returns_none(self) -> None:
        subscription = get_subscription_service()(token="unknown-subscription-token")

        self.assertIsNone(subscription)
