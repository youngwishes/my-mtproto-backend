from __future__ import annotations

import uuid
import copy
from datetime import timedelta
from unittest.mock import Mock

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vpn.enums import VPNAccessState
from apps.vpn.services.deactivate_refund import DeactivateVPNRefundService
from apps.vpn.services.expire_accesses import ExpireVPNAccessesService
from apps.vpn.services.reissue import ReissueVPNAccessService
from apps.vpn.exceptions import (
    VPNAccessExpired,
    VPNReissueConflict,
    VPNReissueInProgress,
    VPNReissueNotEligible,
)
from apps.vpn.tests.factories import VPNAccessFactory


class ReissueVPNAccessServiceTest(TestCase):
    def test_stages_new_uuid_and_preserves_token_and_published_pair(self) -> None:
        old_uuid = uuid.uuid4()
        access = VPNAccessFactory(
            state=VPNAccessState.READY,
            desired_uuid=old_uuid,
            desired_revision=3,
            published_uuid=old_uuid,
            published_revision=3,
        )
        token = access.subscription_token
        schedule = Mock()

        new_uuid = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        result = ReissueVPNAccessService(
            schedule_reconcile=schedule, generate_uuid=Mock(return_value=new_uuid)
        )(access=access)

        access.refresh_from_db()
        self.assertEqual(result.desired_uuid, new_uuid)
        self.assertEqual(access.subscription_token, token)
        self.assertEqual(access.published_uuid, old_uuid)
        self.assertEqual(access.published_revision, 3)
        self.assertEqual(access.desired_revision, 4)
        self.assertEqual(access.state, VPNAccessState.PREPARING)
        schedule.assert_called_once_with()

    def test_stale_concurrent_reissue_is_rejected(self) -> None:
        credential = uuid.uuid4()
        access = VPNAccessFactory(state=VPNAccessState.READY, published_uuid=credential,
                                  desired_uuid=credential, published_revision=1)
        stale = copy.copy(access)
        access.state_revision += 1
        access.save(update_fields=("state_revision", "updated_at"))

        with self.assertRaises(VPNReissueConflict):
            ReissueVPNAccessService(
                schedule_reconcile=Mock(), generate_uuid=uuid.uuid4
            )(access=stale)

    def test_rejects_in_progress_expired_and_unpublished(self) -> None:
        preparing = VPNAccessFactory()
        with self.assertRaises(VPNReissueInProgress):
            ReissueVPNAccessService(schedule_reconcile=Mock(), generate_uuid=uuid.uuid4)(access=preparing)

        expired_uuid = uuid.uuid4()
        expired = VPNAccessFactory(
            state=VPNAccessState.READY, desired_uuid=expired_uuid,
            published_uuid=expired_uuid, published_revision=1,
            expired_at=timezone.now() - timedelta(seconds=1),
        )
        with self.assertRaises(VPNAccessExpired):
            ReissueVPNAccessService(schedule_reconcile=Mock(), generate_uuid=uuid.uuid4)(access=expired)

        unpublished = VPNAccessFactory(state=VPNAccessState.EXPIRED)
        with self.assertRaises(VPNReissueNotEligible):
            ReissueVPNAccessService(schedule_reconcile=Mock(), generate_uuid=uuid.uuid4)(access=unpublished)


class ExpireVPNAccessesServiceTest(TestCase):
    def test_marks_expired_and_schedules_exact_reconcile(self) -> None:
        credential = uuid.uuid4()
        access = VPNAccessFactory(
            state=VPNAccessState.READY,
            desired_uuid=credential,
            published_uuid=credential,
            published_revision=1,
            expired_at=timezone.now() - timedelta(seconds=1),
        )
        schedule = Mock()

        self.assertEqual(ExpireVPNAccessesService(schedule_reconcile=schedule)(), 1)
        access.refresh_from_db()
        self.assertEqual(access.state, VPNAccessState.EXPIRED)
        schedule.assert_called_once_with()


class DeactivateVPNRefundServiceTest(TestCase):
    def test_is_audited_and_idempotent(self) -> None:
        actor = SystemUserFactory()
        credential = uuid.uuid4()
        access = VPNAccessFactory(state=VPNAccessState.READY, desired_uuid=credential,
                                  published_uuid=credential, published_revision=1)
        schedule = Mock()
        service = DeactivateVPNRefundService(schedule_reconcile=schedule)

        self.assertTrue(service(access=access, actor=actor, reason="provider refund"))
        access.refresh_from_db()
        disabled_at = access.disabled_at
        self.assertEqual(access.state, VPNAccessState.DISABLED_REFUND)
        self.assertEqual(access.disabled_by, actor)
        self.assertEqual(access.disabled_reason, "provider refund")
        self.assertFalse(service(access=access, actor=actor, reason="changed"))
        access.refresh_from_db()
        self.assertEqual(access.disabled_at, disabled_at)
        self.assertEqual(access.disabled_reason, "provider refund")
        schedule.assert_called_once_with()
