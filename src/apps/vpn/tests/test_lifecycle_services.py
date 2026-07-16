from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock

from django.test import TestCase
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from apps.payments.enums import ProductCodeEnum
from apps.payments.models import Payment
from apps.payments.services.dtos import VPNPaymentFulfillmentIn
from apps.payments.tests.factories import PaymentFactory, ProductFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vpn.enums import VPNAccessState
from apps.vpn.models import VPNAccess, VPNPurchase
from apps.vpn.services.deactivate_refund import DeactivateVPNRefundService
from apps.vpn.services.expire_accesses import ExpireVPNAccessesService
from apps.vpn.services.fulfill_purchase import FulfillPurchaseService
from apps.vpn.services.reissue import ReissueVPNAccessService
from apps.vpn.exceptions import (
    VPNAccessExpired,
    VPNRefundConflict,
    VPNRefundPurchaseNotCurrent,
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
        access = VPNAccessFactory(
            state=VPNAccessState.READY,
            published_uuid=credential,
            desired_uuid=credential,
            published_revision=1,
        )
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
            ReissueVPNAccessService(
                schedule_reconcile=Mock(), generate_uuid=uuid.uuid4
            )(access=preparing)

        expired_uuid = uuid.uuid4()
        expired = VPNAccessFactory(
            state=VPNAccessState.READY,
            desired_uuid=expired_uuid,
            published_uuid=expired_uuid,
            published_revision=1,
            expired_at=timezone.now() - timedelta(seconds=1),
        )
        with self.assertRaises(VPNAccessExpired):
            ReissueVPNAccessService(
                schedule_reconcile=Mock(), generate_uuid=uuid.uuid4
            )(access=expired)

        unpublished = VPNAccessFactory(state=VPNAccessState.EXPIRED)
        with self.assertRaises(VPNReissueNotEligible):
            ReissueVPNAccessService(
                schedule_reconcile=Mock(), generate_uuid=uuid.uuid4
            )(access=unpublished)


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
    def _ready_access(self, **overrides: object) -> VPNAccess:
        credential = uuid.uuid4()
        values = {
            "state": VPNAccessState.READY,
            "desired_uuid": credential,
            "published_uuid": credential,
            "published_revision": 1,
        }
        values.update(overrides)
        return VPNAccessFactory(**values)

    def _service(self, *, schedule: Mock) -> DeactivateVPNRefundService:
        return DeactivateVPNRefundService(schedule_reconcile=schedule)

    def _purchase(self, *, access: VPNAccess) -> VPNPurchase:
        product = ProductFactory(code=ProductCodeEnum.VLESS_30D)
        payment = PaymentFactory(user=access.user, product=product, key=None)
        return VPNPurchase.objects.create(
            payment=payment,
            access=access,
            period_days=30,
            expired_at_after=access.expired_at,
        )

    def _fulfillment(self, *, callbacks: list[object]) -> FulfillPurchaseService:
        return FulfillPurchaseService(
            get_access=lambda *, user_id: VPNAccess.objects.filter(
                user_id=user_id
            ).first(),
            get_purchase=lambda *, payment_id: VPNPurchase.objects.filter(
                payment_id=payment_id
            )
            .select_related("access")
            .first(),
            create_access=VPNAccess.objects.create,
            save_access=lambda *, access, update_fields: access.save(
                update_fields=update_fields
            ),
            create_purchase=VPNPurchase.objects.create,
            register_after_commit=callbacks.append,
            schedule_delivery=Mock(),
        )

    @staticmethod
    def _fulfillment_input(
        *, payment: Payment, accepted_at: datetime
    ) -> VPNPaymentFulfillmentIn:
        return VPNPaymentFulfillmentIn(
            receipt_id=202,
            payment_id=payment.pk,
            user_id=payment.user_id,
            accepted_at=accepted_at,
        )

    def test_is_audited_on_purchase_and_idempotent(self) -> None:
        actor = SystemUserFactory()
        credential = uuid.uuid4()
        access = VPNAccessFactory(
            state=VPNAccessState.READY,
            desired_uuid=credential,
            published_uuid=credential,
            published_revision=1,
        )
        purchase = self._purchase(access=access)
        schedule = Mock()
        service = self._service(schedule=schedule)

        self.assertTrue(
            service(purchase=purchase, actor=actor, reason="provider refund")
        )
        access.refresh_from_db()
        purchase.refresh_from_db()
        disabled_at = access.disabled_at
        self.assertEqual(access.state, VPNAccessState.DISABLED_REFUND)
        self.assertEqual(access.state_revision, 2)
        self.assertEqual(access.disabled_by, actor)
        self.assertEqual(access.disabled_reason, "provider refund")
        self.assertEqual(purchase.refunded_by, actor)
        self.assertEqual(purchase.refund_reason, "provider refund")
        self.assertEqual(purchase.refunded_at, disabled_at)
        self.assertFalse(service(purchase=purchase, actor=actor, reason="changed"))
        access.refresh_from_db()
        purchase.refresh_from_db()
        self.assertEqual(access.disabled_at, disabled_at)
        self.assertEqual(access.disabled_reason, "provider refund")
        self.assertEqual(purchase.refunded_at, disabled_at)
        self.assertEqual(purchase.refund_reason, "provider refund")
        schedule.assert_called_once_with()

    def test_refund_of_non_current_purchase_is_blocked_without_mutation(self) -> None:
        actor = SystemUserFactory()
        access = self._ready_access()
        older = self._purchase(access=access)
        newer_payment = PaymentFactory(user=access.user, product=older.payment.product)
        VPNPurchase.objects.create(
            payment=newer_payment,
            access=access,
            period_days=30,
            expired_at_after=access.expired_at + timedelta(days=30),
        )
        schedule = Mock()

        with self.assertRaises(VPNRefundPurchaseNotCurrent):
            self._service(schedule=schedule)(
                purchase=older,
                actor=actor,
                reason="old payment refund",
            )

        access.refresh_from_db()
        older.refresh_from_db()
        self.assertEqual(access.state, VPNAccessState.READY)
        self.assertIsNone(older.refunded_at)
        schedule.assert_not_called()

    def test_stale_access_revision_blocks_refund_without_partial_audit(self) -> None:
        actor = SystemUserFactory()
        access = self._ready_access()
        purchase = self._purchase(access=access)
        stale_purchase = copy.copy(purchase)
        stale_purchase.access = copy.copy(access)
        access.state_revision += 1
        access.save(update_fields=("state_revision", "updated_at"))
        schedule = Mock()

        with self.assertRaises(VPNRefundConflict):
            self._service(schedule=schedule)(
                purchase=stale_purchase,
                actor=actor,
                reason="provider refund",
            )

        access.refresh_from_db()
        purchase.refresh_from_db()
        self.assertEqual(access.state, VPNAccessState.READY)
        self.assertIsNone(purchase.refunded_at)
        schedule.assert_not_called()

    def test_active_term_extension_blocks_stale_refund_cas_without_partial_audit(
        self,
    ) -> None:
        actor = SystemUserFactory()
        access = self._ready_access()
        purchase = self._purchase(access=access)
        stale_purchase = copy.copy(purchase)
        stale_purchase.access = copy.copy(access)
        access.expired_at += timedelta(days=30)
        access.save(update_fields=("expired_at", "updated_at"))
        schedule = Mock()

        with self.assertRaises(VPNRefundConflict):
            self._service(schedule=schedule)(
                purchase=stale_purchase,
                actor=actor,
                reason="provider refund",
            )

        access.refresh_from_db()
        purchase.refresh_from_db()
        self.assertEqual(access.state, VPNAccessState.READY)
        self.assertIsNone(purchase.refunded_at)
        self.assertIsNone(purchase.refunded_by)
        self.assertIsNone(purchase.refund_reason)
        schedule.assert_not_called()

    def test_sqlite_write_contention_is_reported_as_domain_conflict(self) -> None:
        actor = SystemUserFactory()
        purchase = self._purchase(access=self._ready_access())
        schedule = Mock()
        service = DeactivateVPNRefundService(
            schedule_reconcile=schedule,
            deactivate_conditionally=Mock(
                side_effect=OperationalError("database is locked")
            ),
        )

        with self.assertRaises(VPNRefundConflict):
            service(
                purchase=purchase,
                actor=actor,
                reason="provider refund",
            )

        purchase.refresh_from_db()
        self.assertIsNone(purchase.refunded_at)
        schedule.assert_not_called()

    def test_refund_audit_constraint_rejects_every_partial_combination(self) -> None:
        actor = SystemUserFactory()
        now = timezone.now()
        product = ProductFactory(code=ProductCodeEnum.VLESS_30D)
        partial_updates = (
            {"refunded_at": now, "refunded_by_id": actor.pk, "refund_reason": None},
            {"refunded_at": now, "refunded_by_id": None, "refund_reason": "refund"},
            {
                "refunded_at": None,
                "refunded_by_id": actor.pk,
                "refund_reason": "refund",
            },
            {"refunded_at": now, "refunded_by_id": actor.pk, "refund_reason": ""},
        )
        purchases = tuple(
            VPNPurchase.objects.create(
                payment=PaymentFactory(
                    user=(access := self._ready_access()).user,
                    product=product,
                    key=None,
                ),
                access=access,
                period_days=30,
                expired_at_after=access.expired_at,
            )
            for _ in partial_updates
        )

        for index, (purchase, updates) in enumerate(
            zip(purchases, partial_updates, strict=True)
        ):
            with self.subTest(index=index), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    VPNPurchase.objects.filter(pk=purchase.pk).update(**updates)

    def test_distinct_payment_reactivates_refunded_access_and_preserves_audit(
        self,
    ) -> None:
        actor = SystemUserFactory()
        accepted_at = timezone.now()
        access = self._ready_access(
            expired_at=accepted_at + timedelta(days=5),
        )
        refunded_purchase = self._purchase(access=access)
        self._service(schedule=Mock())(
            purchase=refunded_purchase,
            actor=actor,
            reason="provider refund",
        )
        access.refresh_from_db()
        revision_after_refund = access.state_revision
        new_payment = PaymentFactory(
            user=access.user,
            product=refunded_purchase.payment.product,
            key=None,
        )
        callbacks: list[object] = []
        fulfillment = self._fulfillment(callbacks=callbacks)

        result = fulfillment(
            purchase=self._fulfillment_input(
                payment=new_payment,
                accepted_at=accepted_at,
            )
        )

        access.refresh_from_db()
        refunded_purchase.refresh_from_db()
        self.assertEqual(access.state, VPNAccessState.PREPARING)
        self.assertEqual(access.state_revision, revision_after_refund + 1)
        self.assertIsNone(access.disabled_at)
        self.assertIsNone(access.disabled_by)
        self.assertEqual(access.disabled_reason, "")
        self.assertIsNotNone(refunded_purchase.refunded_at)
        self.assertEqual(refunded_purchase.refund_reason, "provider refund")
        self.assertFalse(result.is_ready)
        self.assertEqual(len(callbacks), 1)

        replay = fulfillment(
            purchase=self._fulfillment_input(
                payment=new_payment,
                accepted_at=accepted_at,
            )
        )
        access.refresh_from_db()
        self.assertEqual(replay, result)
        self.assertEqual(access.state_revision, revision_after_refund + 1)
