from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from unittest import mock
from uuid import UUID, uuid4

from django.conf import settings
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.utils import timezone

from apps.payments.enums import (
    PaymentKindEnum,
    PaymentProviderEnum,
    PlategaPaymentIntentStatusEnum,
    ProductCodeEnum,
)
from apps.payments.exceptions import PlategaPaymentRetryable
from apps.payments.models import GiftCertificate, Payment
from apps.payments.services import CreatePaymentService
from apps.payments.services.apply_platega_payment import ApplyPlategaPaymentService
from apps.payments.services.dtos import ValidatedPlategaPaymentDTO
from apps.payments.services.extend_key_service import get_extend_key_service
from apps.payments.services.gift_certificates import (
    get_create_gift_certificate_service,
)
from apps.payments.tests.factories import PlategaPaymentIntentFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.vds.services import get_issue_key_on_commit_service
from apps.vds.tests.factories import MTPRotoKeyFactory
from apps.vpn.models import VPNSubscription
from apps.vpn.services.fulfill_vpn_purchase_service import (
    FulfillVPNPurchaseService,
)


class TestPlategaPaymentRetryable(SimpleTestCase):
    def test_exposes_only_safe_retry_reason(self) -> None:
        error = PlategaPaymentRetryable("0", reason_code="processing")

        self.assertEqual(error.telegram_id, "0")
        self.assertEqual(error.context, {"reason_code": "processing"})


class ApplyPlategaPaymentServiceMixin:
    now = datetime(2026, 8, 8, 12, 30, tzinfo=UTC)

    def build_service(
        self,
        *,
        enqueue_notification: mock.Mock | None = None,
    ) -> ApplyPlategaPaymentService:
        self.schedule_profiles = mock.Mock()
        self.enqueue_notification = enqueue_notification or mock.Mock()
        return ApplyPlategaPaymentService(
            create_payment_service=CreatePaymentService(
                extend_key_service=get_extend_key_service(),
                issue_key_service=get_issue_key_on_commit_service(),
                notify_success=mock.Mock(),
            ),
            fulfill_vpn_purchase_service=FulfillVPNPurchaseService(
                schedule_profiles=self.schedule_profiles,
                subscription_base_url="https://vpn.example",
            ),
            create_gift_certificate_service=get_create_gift_certificate_service(),
            enqueue_notification=self.enqueue_notification,
            clock=lambda: self.now,
        )

    @staticmethod
    def validated(
        *, intent_id: int, transaction_id: UUID
    ) -> ValidatedPlategaPaymentDTO:
        return ValidatedPlategaPaymentDTO(
            intent_id=intent_id,
            transaction_id=transaction_id,
        )


class TestApplyPlategaPaymentService(ApplyPlategaPaymentServiceMixin, TestCase):
    def setUp(self) -> None:
        self.service = self.build_service()

    def assert_safe_retryable(
        self,
        *,
        error: PlategaPaymentRetryable,
        raw_text: str,
    ) -> None:
        self.assertEqual(
            error.context,
            {"reason_code": "fulfillment_retryable"},
        )
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        self.assertNotIn(raw_text, repr(error))
        self.assertNotIn(raw_text, str(error))
        self.assertNotIn(raw_text, repr(error.to_dict()))

    @mock.patch("apps.vds.services.issue_key_service.push_key_to_servers_task.delay")
    def test_each_kind_uses_existing_fulfillment_once_with_platega_identity(
        self,
        push_key: mock.Mock,
    ) -> None:
        cases = (
            (PaymentKindEnum.SUBSCRIPTION, ProductCodeEnum.MTPROTO_30D),
            (PaymentKindEnum.VPN_SUBSCRIPTION, ProductCodeEnum.VPN_30D),
            (PaymentKindEnum.GIFT_CERTIFICATE, ProductCodeEnum.MTPROTO_30D),
        )

        for offset, (kind, product_code) in enumerate(cases, start=1):
            with self.subTest(kind=kind):
                user = SystemUserFactory(username=str(900_000_000 + offset))
                transaction_id = uuid4()
                intent = PlategaPaymentIntentFactory(
                    initiator=user,
                    purchase_kind=kind,
                    product_code=product_code,
                    status=PlategaPaymentIntentStatusEnum.ACTIVE,
                    provider_transaction_id=transaction_id,
                )
                validated = self.validated(
                    intent_id=intent.pk,
                    transaction_id=transaction_id,
                )

                with self.captureOnCommitCallbacks(execute=True):
                    result = self.service(payment=validated)

                self.assertTrue(result.fulfilled)
                self.assertFalse(result.already_fulfilled)
                stored = Payment.objects.get(
                    provider=PaymentProviderEnum.PLATEGA,
                    charge_id=str(transaction_id),
                    kind=kind,
                )
                self.assertEqual(stored.user, user)
                intent.refresh_from_db()
                self.assertEqual(intent.payment, stored)
                self.assertEqual(intent.status, PlategaPaymentIntentStatusEnum.FULFILLED)
                self.assertEqual(intent.notification_queued_at, self.now)

                if kind == PaymentKindEnum.SUBSCRIPTION:
                    self.assertEqual(MTPRotoKey.objects.filter(user=user).count(), 1)
                elif kind == PaymentKindEnum.VPN_SUBSCRIPTION:
                    self.assertEqual(VPNSubscription.objects.filter(user=user).count(), 1)
                else:
                    self.assertEqual(GiftCertificate.objects.filter(buyer=user).count(), 1)

                duplicate = self.service(payment=validated)
                self.assertFalse(duplicate.fulfilled)
                self.assertTrue(duplicate.already_fulfilled)
                self.assertEqual(
                    Payment.objects.filter(
                        provider=PaymentProviderEnum.PLATEGA,
                        charge_id=str(transaction_id),
                    ).count(),
                    1,
                )

        self.assertEqual(self.enqueue_notification.call_count, 3)
        push_key.assert_called_once()

    @mock.patch("apps.vds.services.issue_key_service.push_key_to_servers_task.delay")
    def test_late_expired_confirmation_does_not_touch_newer_active_intent(
        self,
        push_key: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="900000010")
        old_transaction_id = uuid4()
        old = PlategaPaymentIntentFactory(
            initiator=user,
            status=PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED,
            provider_transaction_id=old_transaction_id,
        )
        newer = PlategaPaymentIntentFactory(
            initiator=user,
            status=PlategaPaymentIntentStatusEnum.ACTIVE,
            provider_transaction_id=uuid4(),
            provider_expires_at=self.now + timedelta(minutes=15),
        )

        with self.captureOnCommitCallbacks(execute=True):
            result = self.service(
                payment=self.validated(
                    intent_id=old.pk,
                    transaction_id=old_transaction_id,
                )
            )

        old.refresh_from_db()
        newer.refresh_from_db()
        self.assertTrue(result.fulfilled)
        self.assertEqual(old.status, PlategaPaymentIntentStatusEnum.FULFILLED)
        self.assertEqual(newer.status, PlategaPaymentIntentStatusEnum.ACTIVE)
        self.assertIsNone(newer.payment_id)
        push_key.assert_called_once()

    def test_processing_intent_is_retryable_without_domain_changes(self) -> None:
        transaction_id = uuid4()
        intent = PlategaPaymentIntentFactory(
            status=PlategaPaymentIntentStatusEnum.PROCESSING,
            provider_transaction_id=transaction_id,
        )

        with self.assertRaises(PlategaPaymentRetryable) as raised:
            self.service(
                payment=self.validated(
                    intent_id=intent.pk,
                    transaction_id=transaction_id,
                )
            )

        self.assertEqual(raised.exception.context, {"reason_code": "processing"})
        self.assertFalse(Payment.objects.exists())

    @mock.patch("apps.vds.services.issue_key_service.push_key_to_servers_task.delay")
    def test_mtproto_confirmation_extends_existing_key_once(
        self,
        push_key: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="900000020")
        original_expiry = timezone.now() + timedelta(days=10)
        key = MTPRotoKeyFactory(user=user, expired_date=original_expiry)
        transaction_id = uuid4()
        intent = PlategaPaymentIntentFactory(
            initiator=user,
            status=PlategaPaymentIntentStatusEnum.ACTIVE,
            provider_transaction_id=transaction_id,
        )

        with self.captureOnCommitCallbacks(execute=True):
            self.service(
                payment=self.validated(
                    intent_id=intent.pk,
                    transaction_id=transaction_id,
                )
            )
        self.service(
            payment=self.validated(
                intent_id=intent.pk,
                transaction_id=transaction_id,
            )
        )

        key.refresh_from_db()
        self.assertEqual(
            key.expired_date,
            original_expiry + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
        )
        self.assertEqual(
            Payment.objects.filter(
                provider=PaymentProviderEnum.PLATEGA,
                charge_id=str(transaction_id),
            ).count(),
            1,
        )
        push_key.assert_not_called()

    def test_database_failure_is_normalized_and_marks_intent_retryable(self) -> None:
        storage_error = "sensitive identity storage detail"
        transaction_id = uuid4()
        intent = PlategaPaymentIntentFactory(
            status=PlategaPaymentIntentStatusEnum.ACTIVE,
            provider_transaction_id=transaction_id,
        )

        with mock.patch(
            "apps.payments.services.apply_platega_payment.get_payment_by_identity",
            side_effect=OperationalError(storage_error),
        ), self.assertRaises(PlategaPaymentRetryable) as raised:
            self.service(
                payment=self.validated(
                    intent_id=intent.pk,
                    transaction_id=transaction_id,
                )
            )

        intent.refresh_from_db()
        self.assert_safe_retryable(
            error=raised.exception,
            raw_text=storage_error,
        )
        self.assertEqual(intent.status, PlategaPaymentIntentStatusEnum.RETRYABLE)
        self.assertEqual(intent.last_error_code, "fulfillment_retryable")
        self.assertFalse(Payment.objects.exists())
        self.enqueue_notification.assert_not_called()

    @mock.patch("apps.core.decorators._log_service_error")
    def test_callback_fulfillment_errors_never_log_telegram_payload(
        self,
        error_logger: mock.Mock,
    ) -> None:
        cases = (
            (
                PaymentKindEnum.SUBSCRIPTION,
                ProductCodeEnum.MTPROTO_30D,
                mock.patch(
                    "apps.payments.services.create_payment_service.get_user_by_username",
                    return_value=None,
                ),
            ),
            (
                PaymentKindEnum.VPN_SUBSCRIPTION,
                "invalid_product",
                nullcontext(),
            ),
            (
                PaymentKindEnum.GIFT_CERTIFICATE,
                ProductCodeEnum.MTPROTO_30D,
                mock.patch(
                    "apps.payments.services.gift_certificates.get_user_by_username",
                    return_value=None,
                ),
            ),
        )

        for offset, (kind, product_code, failure) in enumerate(cases, start=1):
            with self.subTest(kind=kind), failure:
                transaction_id = uuid4()
                intent = PlategaPaymentIntentFactory(
                    initiator=SystemUserFactory(
                        username=str(900_000_300 + offset),
                    ),
                    purchase_kind=kind,
                    product_code=product_code,
                    status=PlategaPaymentIntentStatusEnum.ACTIVE,
                    provider_transaction_id=transaction_id,
                )

                with self.assertRaises(PlategaPaymentRetryable):
                    self.service(
                        payment=self.validated(
                            intent_id=intent.pk,
                            transaction_id=transaction_id,
                        )
                    )

                error_logger.assert_not_called()
                intent.refresh_from_db()
                self.assertEqual(
                    intent.status,
                    PlategaPaymentIntentStatusEnum.RETRYABLE,
                )

    def test_initial_storage_failure_is_safely_normalized(self) -> None:
        storage_error = "sensitive initial lookup detail"

        with mock.patch(
            "apps.payments.services.apply_platega_payment.get_platega_intent_by_id",
            side_effect=OperationalError(storage_error),
        ), self.assertRaises(PlategaPaymentRetryable) as raised:
            self.service(
                payment=self.validated(
                    intent_id=999,
                    transaction_id=uuid4(),
                )
            )

        self.assertEqual(
            raised.exception.context,
            {"reason_code": "fulfillment_retryable"},
        )
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        self.assertNotIn(storage_error, repr(raised.exception))
        self.assertNotIn(storage_error, str(raised.exception))
        self.assertNotIn(storage_error, repr(raised.exception.to_dict()))

    @mock.patch("apps.vds.services.issue_key_service.push_key_to_servers_task.delay")
    def test_failure_after_each_domain_write_rolls_back_and_becomes_retryable(
        self,
        push_key: mock.Mock,
    ) -> None:
        cases = (
            (PaymentKindEnum.SUBSCRIPTION, ProductCodeEnum.MTPROTO_30D),
            (PaymentKindEnum.VPN_SUBSCRIPTION, ProductCodeEnum.VPN_30D),
            (PaymentKindEnum.GIFT_CERTIFICATE, ProductCodeEnum.MTPROTO_30D),
        )

        for offset, (kind, product_code) in enumerate(cases, start=1):
            with self.subTest(kind=kind):
                user = SystemUserFactory(username=str(900_000_100 + offset))
                transaction_id = uuid4()
                intent = PlategaPaymentIntentFactory(
                    initiator=user,
                    purchase_kind=kind,
                    product_code=product_code,
                    status=PlategaPaymentIntentStatusEnum.ACTIVE,
                    provider_transaction_id=transaction_id,
                )

                with mock.patch(
                    "apps.payments.services.apply_platega_payment.get_payment_by_identity",
                    return_value=None,
                ), self.assertRaises(PlategaPaymentRetryable) as raised:
                    self.service(
                        payment=self.validated(
                            intent_id=intent.pk,
                            transaction_id=transaction_id,
                        )
                    )

                intent.refresh_from_db()
                self.assertEqual(
                    raised.exception.context,
                    {"reason_code": "fulfillment_retryable"},
                )
                self.assertEqual(intent.status, PlategaPaymentIntentStatusEnum.RETRYABLE)
                self.assertEqual(intent.last_error_code, "fulfillment_retryable")
                self.assertFalse(
                    Payment.objects.filter(
                        provider=PaymentProviderEnum.PLATEGA,
                        charge_id=str(transaction_id),
                    ).exists()
                )
                self.assertFalse(MTPRotoKey.objects.filter(user=user).exists())
                self.assertFalse(VPNSubscription.objects.filter(user=user).exists())
                self.assertFalse(GiftCertificate.objects.filter(buyer=user).exists())

        push_key.assert_not_called()
        self.enqueue_notification.assert_not_called()

    @mock.patch("apps.vds.services.issue_key_service.push_key_to_servers_task.delay")
    def test_retryable_intent_can_recover(self, push_key: mock.Mock) -> None:
        transaction_id = uuid4()
        intent = PlategaPaymentIntentFactory(
            status=PlategaPaymentIntentStatusEnum.RETRYABLE,
            provider_transaction_id=transaction_id,
            last_error_code="fulfillment_retryable",
        )

        with self.captureOnCommitCallbacks(execute=True):
            result = self.service(
                payment=self.validated(
                    intent_id=intent.pk,
                    transaction_id=transaction_id,
                )
            )

        intent.refresh_from_db()
        self.assertTrue(result.fulfilled)
        self.assertEqual(intent.status, PlategaPaymentIntentStatusEnum.FULFILLED)
        self.assertEqual(intent.last_error_code, "")
        push_key.assert_called_once()

    def test_enqueue_is_registered_only_after_outer_commit(self) -> None:
        transaction_id = uuid4()
        intent = PlategaPaymentIntentFactory(
            purchase_kind=PaymentKindEnum.VPN_SUBSCRIPTION,
            product_code=ProductCodeEnum.VPN_30D,
            status=PlategaPaymentIntentStatusEnum.ACTIVE,
            provider_transaction_id=transaction_id,
        )

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.service(
                payment=self.validated(
                    intent_id=intent.pk,
                    transaction_id=transaction_id,
                )
            )
            self.schedule_profiles.assert_not_called()
            self.enqueue_notification.assert_not_called()

        for callback in callbacks:
            callback()

        self.schedule_profiles.assert_called_once()
        self.enqueue_notification.assert_called_once_with(intent_id=intent.pk)

    @mock.patch("apps.vds.services.issue_key_service.push_key_to_servers_task.delay")
    def test_publish_failure_clears_marker_and_duplicate_republishes(
        self,
        push_key: mock.Mock,
    ) -> None:
        transaction_id = uuid4()
        intent = PlategaPaymentIntentFactory(
            status=PlategaPaymentIntentStatusEnum.ACTIVE,
            provider_transaction_id=transaction_id,
        )
        publish_error = "sensitive publish detail"
        failing_enqueue = mock.Mock(side_effect=RuntimeError(publish_error))
        service = self.build_service(enqueue_notification=failing_enqueue)
        validated = self.validated(
            intent_id=intent.pk,
            transaction_id=transaction_id,
        )

        with self.assertRaises(PlategaPaymentRetryable) as raised:
            with self.captureOnCommitCallbacks(execute=True):
                service(payment=validated)

        intent.refresh_from_db()
        self.assert_safe_retryable(
            error=raised.exception,
            raw_text=publish_error,
        )
        self.assertEqual(intent.status, PlategaPaymentIntentStatusEnum.FULFILLED)
        self.assertIsNotNone(intent.payment_id)
        self.assertIsNone(intent.notification_queued_at)

        recovered_enqueue = mock.Mock()
        recovered = self.build_service(enqueue_notification=recovered_enqueue)
        with self.captureOnCommitCallbacks(execute=True):
            result = recovered(payment=validated)

        intent.refresh_from_db()
        self.assertFalse(result.fulfilled)
        self.assertTrue(result.already_fulfilled)
        self.assertEqual(intent.notification_queued_at, self.now)
        recovered_enqueue.assert_called_once_with(intent_id=intent.pk)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        push_key.assert_called_once()

    def test_publish_failure_does_not_clear_a_different_marker(self) -> None:
        transaction_id = uuid4()
        intent = PlategaPaymentIntentFactory(
            status=PlategaPaymentIntentStatusEnum.ACTIVE,
            provider_transaction_id=transaction_id,
        )
        stored = Payment.objects.create(
            user=intent.initiator,
            key=None,
            charge_id=str(transaction_id),
            provider=PaymentProviderEnum.PLATEGA,
            kind=PaymentKindEnum.SUBSCRIPTION,
        )
        type(intent).objects.filter(pk=intent.pk).update(
            status=PlategaPaymentIntentStatusEnum.FULFILLED,
            payment=stored,
            notification_queued_at=None,
        )
        other_marker = self.now + timedelta(seconds=1)

        def replace_marker_then_fail(*, intent_id: int) -> None:
            type(intent).objects.filter(pk=intent_id).update(
                notification_queued_at=other_marker,
            )
            raise RuntimeError("provider detail")

        service = self.build_service(
            enqueue_notification=mock.Mock(side_effect=replace_marker_then_fail),
        )

        with self.assertRaises(PlategaPaymentRetryable):
            with self.captureOnCommitCallbacks(execute=True):
                service(
                    payment=self.validated(
                        intent_id=intent.pk,
                        transaction_id=transaction_id,
                    )
                )

        intent.refresh_from_db()
        self.assertEqual(intent.notification_queued_at, other_marker)


class TestApplyPlategaPaymentCommitFailure(
    ApplyPlategaPaymentServiceMixin,
    TransactionTestCase,
):
    def test_earlier_commit_hook_failure_clears_marker_for_duplicate_retry(
        self,
    ) -> None:
        transaction_id = uuid4()
        intent = PlategaPaymentIntentFactory(
            status=PlategaPaymentIntentStatusEnum.ACTIVE,
            provider_transaction_id=transaction_id,
        )
        validated = self.validated(
            intent_id=intent.pk,
            transaction_id=transaction_id,
        )
        enqueue = mock.Mock()
        service = self.build_service(enqueue_notification=enqueue)
        publish_error = "sensitive issue-key publish detail"

        with mock.patch(
            "apps.vds.services.issue_key_service.push_key_to_servers_task"
        ) as push_task:
            push_task.delay.side_effect = RuntimeError(publish_error)

            with self.assertRaises(PlategaPaymentRetryable) as raised:
                service(payment=validated)

            intent.refresh_from_db()
            self.assertEqual(
                raised.exception.context,
                {"reason_code": "fulfillment_retryable"},
            )
            self.assertIsNone(raised.exception.__cause__)
            self.assertIsNone(raised.exception.__context__)
            self.assertNotIn(publish_error, repr(raised.exception))
            self.assertNotIn(publish_error, str(raised.exception))
            self.assertNotIn(publish_error, repr(raised.exception.to_dict()))
            self.assertEqual(
                intent.status,
                PlategaPaymentIntentStatusEnum.FULFILLED,
            )
            self.assertIsNotNone(intent.payment_id)
            self.assertIsNone(intent.notification_queued_at)
            self.assertEqual(Payment.objects.count(), 1)
            self.assertEqual(MTPRotoKey.objects.count(), 1)
            enqueue.assert_not_called()

            push_task.delay.side_effect = None
            result = service(payment=validated)

        intent.refresh_from_db()
        self.assertFalse(result.fulfilled)
        self.assertTrue(result.already_fulfilled)
        self.assertEqual(intent.notification_queued_at, self.now)
        enqueue.assert_called_once_with(intent_id=intent.pk)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(MTPRotoKey.objects.count(), 1)
