from __future__ import annotations

from datetime import timedelta
from unittest import mock

from celery.exceptions import Retry
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.payments.enums import (
    PaymentKindEnum,
    PaymentProviderEnum,
    PlategaPaymentIntentStatusEnum,
)
from apps.payments.services import get_create_payment_service
from apps.payments.services.dtos import CreatePaymentIn
from apps.payments.tasks import notify_platega_purchase_task
from apps.payments.tests.factories import (
    GiftCertificateFactory,
    PaymentFactory,
    PlategaPaymentIntentFactory,
)
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory
from apps.vpn.tests.factories import VPNSubscriptionFactory


_TELEGRAM_TRANSPORT = (
    "apps.notifications.services.send_notification_service.send_telegram_message"
)


class TestNotifyPlategaPurchaseTask(TestCase):
    @mock.patch(_TELEGRAM_TRANSPORT)
    def test_mtproto_issue_uses_existing_template_and_marks_sent(
        self,
        send: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="200001")
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=timezone.now() + timedelta(days=30),
        )
        payment = PaymentFactory(
            user=user,
            key=key,
            kind=PaymentKindEnum.SUBSCRIPTION,
            provider=PaymentProviderEnum.PLATEGA,
        )
        intent = PlategaPaymentIntentFactory(
            initiator=user,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
            status=PlategaPaymentIntentStatusEnum.FULFILLED,
            payment=payment,
            fulfilled_at=timezone.now(),
            notification_queued_at=timezone.now(),
        )

        notify_platega_purchase_task.run(intent.pk)

        self.assertIn(
            key.expired_date.date().strftime("%d.%m.%y"),
            send.call_args.kwargs["text"],
        )
        intent.refresh_from_db()
        self.assertIsNotNone(intent.notification_sent_at)

    @mock.patch(_TELEGRAM_TRANSPORT)
    def test_mtproto_extension_uses_current_stored_key_expiry(
        self,
        send: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="200002")
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=timezone.now() + timedelta(days=30),
        )
        payment = PaymentFactory(
            user=user,
            key=key,
            kind=PaymentKindEnum.SUBSCRIPTION,
            provider=PaymentProviderEnum.PLATEGA,
        )
        intent = PlategaPaymentIntentFactory(
            initiator=user,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
            status=PlategaPaymentIntentStatusEnum.FULFILLED,
            payment=payment,
            fulfilled_at=timezone.now(),
            notification_queued_at=timezone.now(),
        )
        get_create_payment_service()(
            payment=CreatePaymentIn(
                username=user.username,
                charge_id="later-stars-extension",
                provider=PaymentProviderEnum.STARS,
            ),
            send_success_notification=False,
        )

        notify_platega_purchase_task.run(intent.pk)

        key.refresh_from_db()
        payment.refresh_from_db()
        self.assertIsNone(payment.key)
        self.assertIn(
            key.expired_date.date().strftime("%d.%m.%y"),
            send.call_args.kwargs["text"],
        )

    @override_settings(VPN_SUBSCRIPTION_BASE_URL="https://vpn.example")
    @mock.patch(_TELEGRAM_TRANSPORT)
    def test_vpn_uses_stored_expiry_and_permanent_url_then_marks_sent(
        self,
        send: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="200003")
        subscription = VPNSubscriptionFactory(user=user)
        payment = PaymentFactory(
            user=user,
            kind=PaymentKindEnum.VPN_SUBSCRIPTION,
            provider=PaymentProviderEnum.PLATEGA,
        )
        intent = PlategaPaymentIntentFactory(
            initiator=user,
            purchase_kind=PaymentKindEnum.VPN_SUBSCRIPTION,
            status=PlategaPaymentIntentStatusEnum.FULFILLED,
            payment=payment,
            fulfilled_at=timezone.now(),
            notification_queued_at=timezone.now(),
        )

        notify_platega_purchase_task.run(intent.pk)

        text = send.call_args.kwargs["text"]
        self.assertIn(
            subscription.expired_at.strftime("%d.%m.%Y %H:%M UTC"),
            text,
        )
        self.assertIn(
            "https://vpn.example/api/v1/vpn/subscriptions/"
            f"{subscription.token}/",
            text,
        )
        intent.refresh_from_db()
        self.assertIsNotNone(intent.notification_sent_at)

    @mock.patch(_TELEGRAM_TRANSPORT)
    def test_gift_uses_stored_code_then_marks_sent(self, send: mock.Mock) -> None:
        user = SystemUserFactory(username="200004")
        payment = PaymentFactory(
            user=user,
            kind=PaymentKindEnum.GIFT_CERTIFICATE,
            provider=PaymentProviderEnum.PLATEGA,
        )
        certificate = GiftCertificateFactory(buyer=user, payment=payment)
        intent = PlategaPaymentIntentFactory(
            initiator=user,
            purchase_kind=PaymentKindEnum.GIFT_CERTIFICATE,
            status=PlategaPaymentIntentStatusEnum.FULFILLED,
            payment=payment,
            fulfilled_at=timezone.now(),
            notification_queued_at=timezone.now(),
        )

        notify_platega_purchase_task.run(intent.pk)

        self.assertIn(certificate.code, send.call_args.kwargs["text"])
        intent.refresh_from_db()
        self.assertIsNotNone(intent.notification_sent_at)

    @mock.patch(_TELEGRAM_TRANSPORT)
    def test_unqueued_or_already_sent_intent_is_a_noop(
        self,
        send: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="200005")
        key = MTPRotoKeyFactory(user=user)
        payment = PaymentFactory(
            user=user,
            key=key,
            kind=PaymentKindEnum.SUBSCRIPTION,
            provider=PaymentProviderEnum.PLATEGA,
        )
        unqueued = PlategaPaymentIntentFactory(
            initiator=user,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
            status=PlategaPaymentIntentStatusEnum.FULFILLED,
            payment=payment,
            notification_queued_at=None,
        )
        sent = PlategaPaymentIntentFactory(
            initiator=user,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
            status=PlategaPaymentIntentStatusEnum.FULFILLED,
            payment=PaymentFactory(
                user=SystemUserFactory(username="200006"),
                kind=PaymentKindEnum.SUBSCRIPTION,
                provider=PaymentProviderEnum.PLATEGA,
            ),
            notification_queued_at=timezone.now(),
            notification_sent_at=timezone.now(),
        )

        notify_platega_purchase_task.run(unqueued.pk)
        notify_platega_purchase_task.run(sent.pk)

        send.assert_not_called()
        unqueued.refresh_from_db()
        self.assertIsNone(unqueued.notification_sent_at)

    @mock.patch(
        _TELEGRAM_TRANSPORT,
        side_effect=RuntimeError("telegram failed: result-secret-token"),
    )
    def test_telegram_failure_retries_safely_and_leaves_marker_unsent(
        self,
        send: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="200007")
        key = MTPRotoKeyFactory(user=user, token="result-secret-token")
        payment = PaymentFactory(
            user=user,
            key=key,
            kind=PaymentKindEnum.SUBSCRIPTION,
            provider=PaymentProviderEnum.PLATEGA,
        )
        intent = PlategaPaymentIntentFactory(
            initiator=user,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
            status=PlategaPaymentIntentStatusEnum.FULFILLED,
            payment=payment,
            fulfilled_at=timezone.now(),
            notification_queued_at=timezone.now(),
        )

        with mock.patch.object(
            notify_platega_purchase_task,
            "retry",
            side_effect=Retry(),
        ) as retry, self.assertRaises(Retry) as raised:
            notify_platega_purchase_task.run(intent.pk)

        retry_exc = retry.call_args.kwargs["exc"]
        self.assertEqual(retry.call_args.kwargs["countdown"], 30)
        self.assertNotIn("result-secret-token", str(retry_exc))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        intent.refresh_from_db()
        self.assertIsNone(intent.notification_sent_at)
