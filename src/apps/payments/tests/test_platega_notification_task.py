from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
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
    AppleCashbackPurchaseFactory,
    GiftCertificateFactory,
    PaymentFactory,
    PlategaPaymentIntentFactory,
)
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory
from apps.vpn.tests.factories import VPNSubscriptionFactory


_TELEGRAM_TRANSPORT = (
    "apps.payments.tasks.send_telegram_message"
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
        purchase = AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key=f"platega:{payment.charge_id}:subscription",
            apples_earned=5,
            rate_percent=5,
            balance_after=5,
            eligible_purchase_count_after=4,
            result_expired_at=key.expired_date,
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
            purchase.result_expired_at.date().strftime("%d.%m.%Y"),
            send.call_args.kwargs["text"],
        )
        text = send.call_args.kwargs["text"]
        self.assertIn("Начислено: <b>5 🍏</b>", text)
        self.assertIn("Ставка: <b>5%</b>", text)
        self.assertIn("Баланс: <b>5 🍏</b>", text)
        self.assertIn("Уровень: <b>Садовник</b>", text)
        self.assertIn("Кэшбэк следующей покупки: <b>10%</b>", text)
        self.assertIsNotNone(send.call_args.kwargs["markup"])
        intent.refresh_from_db()
        self.assertIsNotNone(intent.notification_sent_at)

    @mock.patch(_TELEGRAM_TRANSPORT)
    def test_mtproto_extension_uses_saved_purchase_expiry(
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
        original_result_expiry = key.expired_date
        AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key=f"platega:{payment.charge_id}:subscription",
            result_expired_at=original_result_expiry,
        )
        get_create_payment_service()(
            payment=CreatePaymentIn(
                username=user.username,
                charge_id="later-stars-extension",
                provider=PaymentProviderEnum.STARS,
                nominal_rub_amount=Decimal("99.00"),
            ),
        )

        notify_platega_purchase_task.run(intent.pk)

        key.refresh_from_db()
        payment.refresh_from_db()
        self.assertIsNone(payment.key)
        self.assertIn(
            original_result_expiry.date().strftime("%d.%m.%Y"),
            send.call_args.kwargs["text"],
        )
        self.assertNotIn(
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
        subscription = VPNSubscriptionFactory(
            user=user,
            expired_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        )
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
            "31.08.2026, 15:00 МСК",
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
        AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key=f"platega:{payment.charge_id}:gift_certificate",
            apples_earned=10,
            rate_percent=10,
            balance_after=15,
            eligible_purchase_count_after=7,
        )
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
        self.assertIn("Начислено: <b>10 🍏</b>", send.call_args.kwargs["text"])
        self.assertIn("Уровень: <b>Мастер сада</b>", send.call_args.kwargs["text"])
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
        AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key=f"platega:{payment.charge_id}:subscription",
            result_expired_at=key.expired_date,
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

    @mock.patch(_TELEGRAM_TRANSPORT)
    def test_historical_purchase_returns_before_transport(
        self,
        send: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="200008")
        payment = PaymentFactory(
            user=user,
            kind=PaymentKindEnum.SUBSCRIPTION,
            provider=PaymentProviderEnum.PLATEGA,
        )
        AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key=f"platega:{payment.charge_id}:subscription",
            rate_percent=None,
            apples_earned=0,
            balance_after=0,
            eligible_purchase_count_after=1,
            result_expired_at=None,
        )
        intent = PlategaPaymentIntentFactory(
            initiator=user,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
            status=PlategaPaymentIntentStatusEnum.FULFILLED,
            payment=payment,
            notification_queued_at=timezone.now(),
        )

        notify_platega_purchase_task.run(intent.pk)

        send.assert_not_called()
        intent.refresh_from_db()
        self.assertIsNone(intent.notification_sent_at)
