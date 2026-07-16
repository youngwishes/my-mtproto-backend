from __future__ import annotations

from unittest import mock

from django.test import TestCase

from apps.vpn.enums import VPNAccessState, VPNApplyStatus, VPNNodeHealthState
from apps.vpn.services.publish_readiness import get_publish_vpn_readiness_service
from apps.vpn.tests.factories import (
    VPNAccessFactory,
    VPNAccessNodeApplyFactory,
    VPNNodeFactory,
)


class PublishVPNReadinessServiceTests(TestCase):
    def setUp(self) -> None:
        self.access = VPNAccessFactory(state=VPNAccessState.PREPARING)
        self.schedule_notification = mock.Mock()

    def test_no_matching_node_does_not_publish_or_notify(self) -> None:
        get_publish_vpn_readiness_service(
            schedule_notification=self.schedule_notification
        )(access_id=self.access.pk)

        self.access.refresh_from_db()
        self.assertIsNone(self.access.published_revision)
        self.assertEqual(self.access.state, VPNAccessState.PREPARING)
        self.schedule_notification.assert_not_called()

    def test_first_eligible_exact_apply_publishes_and_schedules_notification(
        self,
    ) -> None:
        node = VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            desired_snapshot_revision=4,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=4,
            applied_snapshot_hash="a" * 64,
        )
        VPNAccessNodeApplyFactory(
            access=self.access,
            node=node,
            desired_revision=self.access.desired_revision,
            applied_revision=self.access.desired_revision,
            status=VPNApplyStatus.APPLIED,
        )

        with self.captureOnCommitCallbacks(execute=True):
            published = get_publish_vpn_readiness_service(
                schedule_notification=self.schedule_notification
            )(access_id=self.access.pk)

        self.access.refresh_from_db()
        self.assertTrue(published)
        self.assertEqual(self.access.published_uuid, self.access.desired_uuid)
        self.assertEqual(self.access.published_revision, self.access.desired_revision)
        self.assertEqual(self.access.state, VPNAccessState.READY)
        self.schedule_notification.assert_called_once_with(
            access_id=self.access.pk,
            revision=self.access.desired_revision,
        )

    def test_old_or_wrong_revision_is_ignored(self) -> None:
        node = VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            desired_snapshot_revision=4,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=4,
            applied_snapshot_hash="a" * 64,
        )
        VPNAccessNodeApplyFactory(
            access=self.access,
            node=node,
            desired_revision=self.access.desired_revision + 1,
            applied_revision=self.access.desired_revision + 1,
            status=VPNApplyStatus.APPLIED,
        )

        published = get_publish_vpn_readiness_service(
            schedule_notification=self.schedule_notification
        )(access_id=self.access.pk)

        self.assertFalse(published)
