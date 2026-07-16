from __future__ import annotations

import uuid
import base64
from datetime import timedelta
from unittest.mock import Mock, patch
from redis.exceptions import ConnectionError as RedisConnectionError

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users.tests.factories import SystemUserFactory
from apps.vpn.enums import (
    VPNAccessState,
    VPNApplyStatus,
    VPNDataPlaneState,
    VPNNodeHealthState,
)
from apps.vpn.tests.factories import (
    VPNAccessFactory,
    VPNAccessNodeApplyFactory,
    VPNAccessNodeRevisionEvidenceFactory,
    VPNNodeFactory,
)


class VPNSubscriptionViewTest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

    def _get(self, token: str):
        with patch(
            "apps.vpn.api.v1.views.subscription.get_subscription_throttle",
            return_value=Mock(allow=Mock(return_value=None)),
        ):
            return self.client.get(
                reverse("vpn-subscription", kwargs={"token": token})
            )

    def test_ready_access_returns_only_exact_applied_nodes(self) -> None:
        credential = uuid.uuid4()
        access = VPNAccessFactory(
            state=VPNAccessState.READY,
            desired_uuid=credential,
            published_uuid=credential,
            published_revision=1,
        )
        node = VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            data_plane_state=VPNDataPlaneState.SERVING_READY,
            desired_snapshot_revision=2,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=2,
            applied_snapshot_hash="a" * 64,
        )
        VPNAccessNodeApplyFactory(
            access=access,
            node=node,
            desired_revision=1,
            applied_revision=1,
            status=VPNApplyStatus.APPLIED,
        )
        VPNAccessNodeRevisionEvidenceFactory(
            access=access,
            node=node,
            revision=1,
            applied_revision=1,
            status=VPNApplyStatus.APPLIED,
            is_serving=True,
        )

        response = self._get(access.subscription_token)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(base64.b64decode(response.content).startswith(b"vless://"))
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertTrue(response["Content-Type"].startswith("text/plain"))

    def test_initial_preparing_returns_retryable_503(self) -> None:
        access = VPNAccessFactory(state=VPNAccessState.PREPARING)
        response = self._get(access.subscription_token)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "30")
        self.assertNotIn(access.subscription_token.encode(), response.content)

    def test_hard_data_plane_failure_excludes_previously_serving_node(self) -> None:
        credential = uuid.uuid4()
        access = VPNAccessFactory(
            state=VPNAccessState.READY,
            desired_uuid=credential,
            published_uuid=credential,
            published_revision=1,
        )
        node = VPNNodeFactory(
            data_plane_state=VPNDataPlaneState.UNAVAILABLE,
            desired_snapshot_revision=1,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=1,
            applied_snapshot_hash="a" * 64,
        )
        VPNAccessNodeRevisionEvidenceFactory(
            access=access,
            node=node,
            revision=1,
            applied_revision=1,
            status=VPNApplyStatus.APPLIED,
            is_serving=True,
        )
        response = self._get(access.subscription_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

    def test_expired_and_refunded_are_safe_empty(self) -> None:
        expired = VPNAccessFactory(
            state=VPNAccessState.EXPIRED,
            expired_at=timezone.now() - timedelta(seconds=1),
        )
        response = self._get(expired.subscription_token)
        self.assertEqual((response.status_code, response.content), (200, b""))

        actor = SystemUserFactory()
        refunded = VPNAccessFactory(
            state=VPNAccessState.DISABLED_REFUND,
            disabled_at=timezone.now(),
            disabled_by=actor,
            disabled_reason="refund",
        )
        response = self._get(refunded.subscription_token)
        self.assertEqual((response.status_code, response.content), (200, b""))

    def test_unknown_token_is_404(self) -> None:
        response = self._get("x" * 43)
        self.assertEqual(response.status_code, 404)

    def test_throttled_request_is_429_with_retry_after(self) -> None:
        access = VPNAccessFactory()
        with patch(
            "apps.vpn.api.v1.views.subscription.get_subscription_throttle",
            return_value=Mock(allow=Mock(return_value=17)),
        ):
            response = self.client.get(
                reverse("vpn-subscription", kwargs={"token": access.subscription_token})
            )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "17")

    def test_redis_failure_is_fail_closed_503(self) -> None:
        access = VPNAccessFactory()
        throttle = Mock()
        throttle.allow.side_effect = RedisConnectionError("down")
        with patch(
            "apps.vpn.api.v1.views.subscription.get_subscription_throttle",
            return_value=throttle,
        ):
            response = self.client.get(
                reverse("vpn-subscription", kwargs={"token": access.subscription_token})
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "30")
        self.assertEqual(response["Cache-Control"], "private, no-store")
