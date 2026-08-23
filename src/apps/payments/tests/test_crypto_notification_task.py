from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest import mock

from celery.exceptions import Retry
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.payments.enums import (
    CryptoPaymentIntentStatusEnum,
    PaymentKindEnum,
    PaymentProviderEnum,
)
from apps.payments.tasks import notify_crypto_purchase_task
from apps.payments.services import get_create_payment_service
from apps.payments.services.dtos import CreatePaymentIn
from apps.payments.tests.factories import (
    AppleCashbackPurchaseFactory,
    CryptoPaymentIntentFactory,
    GiftCertificateFactory,
    PaymentFactory,
)
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory
from apps.vpn.tests.factories import VPNSubscriptionFactory


class TestNotifyCryptoPurchaseTask(TestCase):
    @mock.patch("apps.payments.tasks.send_telegram_message")
    def test_mtproto_notification_uses_existing_template_and_marks_sent(
        self,
        send: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="100001")
        key = MTPRotoKeyFactory(user=user, expired_date=timezone.now() + timedelta(days=1))
        payment = PaymentFactory(
            user=key.user,
            key=key,
            kind=PaymentKindEnum.SUBSCRIPTION,
            provider=PaymentProviderEnum.CRYPTO_PAY,
        )
        purchase = AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key=f"crypto_pay:{payment.charge_id}:subscription",
            apples_earned=5,
            rate_percent=5,
            balance_after=5,
            eligible_purchase_count_after=4,
            result_expired_at=key.expired_date,
        )
        intent = CryptoPaymentIntentFactory(
            initiator=key.user,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            payment=payment,
            fulfilled_at=timezone.now(),
        )

        notify_crypto_purchase_task.run(intent.pk)

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
        self.assertLess(text.index("🍏 <b>Кэшбэк</b>"), text.rindex("👇"))
        self.assertTrue(text.rstrip().rsplit("\n\n", 1)[-1].startswith("👇"))
        self.assertIsNotNone(send.call_args.kwargs["markup"])
        intent.refresh_from_db()
        self.assertIsNotNone(intent.notification_sent_at)

    @mock.patch("apps.payments.tasks.send_telegram_message")
    def test_mtproto_renewal_before_delivery_uses_saved_purchase_expiry(
        self, send: mock.Mock
    ) -> None:
        user = SystemUserFactory(username="100005")
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=timezone.now() + timedelta(days=1),
        )
        original_payment = PaymentFactory(
            user=user,
            key=key,
            kind=PaymentKindEnum.SUBSCRIPTION,
            provider=PaymentProviderEnum.CRYPTO_PAY,
        )
        intent = CryptoPaymentIntentFactory(
            initiator=user,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            payment=original_payment,
        )
        original_result_expiry = key.expired_date
        AppleCashbackPurchaseFactory(
            payment=original_payment,
            identity_key=(
                f"crypto_pay:{original_payment.charge_id}:subscription"
            ),
            result_expired_at=original_result_expiry,
        )
        get_create_payment_service()(
            payment=CreatePaymentIn(
                username=user.username,
                charge_id="later-stars-renewal",
                provider=PaymentProviderEnum.STARS,
                nominal_rub_amount=Decimal("99.00"),
            ),
        )

        notify_crypto_purchase_task.run(intent.pk)

        key.refresh_from_db()
        original_payment.refresh_from_db()
        self.assertIsNone(original_payment.key)
        self.assertIn(
            original_result_expiry.date().strftime("%d.%m.%Y"),
            send.call_args.kwargs["text"],
        )
        self.assertNotIn(
            key.expired_date.date().strftime("%d.%m.%y"),
            send.call_args.kwargs["text"],
        )
        intent.refresh_from_db()
        self.assertIsNotNone(intent.notification_sent_at)

    @override_settings(VPN_SUBSCRIPTION_BASE_URL="https://vpn.example")
    @mock.patch("apps.payments.tasks.send_telegram_message")
    def test_vpn_notification_uses_expiry_and_permanent_url_then_marks_sent(
        self,
        send: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="100002")
        subscription = VPNSubscriptionFactory(
            user=user,
            expired_at=datetime(2026, 8, 31, 22, 30, tzinfo=UTC),
        )
        payment = PaymentFactory(
            user=subscription.user,
            kind=PaymentKindEnum.VPN_SUBSCRIPTION,
            provider=PaymentProviderEnum.CRYPTO_PAY,
        )
        intent = CryptoPaymentIntentFactory(
            initiator=subscription.user,
            purchase_kind=PaymentKindEnum.VPN_SUBSCRIPTION,
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            payment=payment,
            fulfilled_at=timezone.now(),
        )

        notify_crypto_purchase_task.run(intent.pk)

        text = send.call_args.kwargs["text"]
        self.assertIn("01.09.2026", text)
        self.assertNotIn("22:30", text)
        self.assertNotIn("МСК", text)
        self.assertIn(
            "https://vpn.example/api/v1/vpn/subscriptions/"
            f"{subscription.token}/",
            text,
        )
        intent.refresh_from_db()
        self.assertIsNotNone(intent.notification_sent_at)

    @mock.patch("apps.payments.tasks.send_telegram_message")
    def test_gift_notification_uses_code_then_marks_sent(
        self,
        send: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="100003")
        payment = PaymentFactory(user=user)
        certificate = GiftCertificateFactory(buyer=user, payment=payment)
        certificate.payment.provider = PaymentProviderEnum.CRYPTO_PAY
        certificate.payment.kind = PaymentKindEnum.GIFT_CERTIFICATE
        certificate.payment.save(update_fields=["provider", "kind"])
        AppleCashbackPurchaseFactory(
            payment=certificate.payment,
            identity_key=(
                f"crypto_pay:{certificate.payment.charge_id}:gift_certificate"
            ),
            apples_earned=10,
            rate_percent=10,
            balance_after=15,
            eligible_purchase_count_after=7,
        )
        intent = CryptoPaymentIntentFactory(
            initiator=certificate.buyer,
            purchase_kind=PaymentKindEnum.GIFT_CERTIFICATE,
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            payment=certificate.payment,
            fulfilled_at=timezone.now(),
        )

        notify_crypto_purchase_task.run(intent.pk)

        self.assertIn(certificate.code, send.call_args.kwargs["text"])
        self.assertIn("Начислено: <b>10 🍏</b>", send.call_args.kwargs["text"])
        self.assertIn("Уровень: <b>Мастер сада</b>", send.call_args.kwargs["text"])
        intent.refresh_from_db()
        self.assertIsNotNone(intent.notification_sent_at)

    @mock.patch(
        "apps.payments.tasks.send_telegram_message",
        side_effect=RuntimeError("telegram unavailable"),
    )
    def test_temporary_send_error_retries_without_marking_sent(
        self,
        send: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="100004")
        key = MTPRotoKeyFactory(user=user, token="result-secret-token")
        payment = PaymentFactory(
            user=key.user,
            key=key,
            kind=PaymentKindEnum.SUBSCRIPTION,
            provider=PaymentProviderEnum.CRYPTO_PAY,
        )
        intent = CryptoPaymentIntentFactory(
            initiator=key.user,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            payment=payment,
            fulfilled_at=timezone.now(),
        )
        AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key=f"crypto_pay:{payment.charge_id}:subscription",
            result_expired_at=key.expired_date,
        )

        with mock.patch.object(
            notify_crypto_purchase_task,
            "retry",
            side_effect=Retry(),
        ) as retry:
            with self.assertRaises(Retry):
                notify_crypto_purchase_task.run(intent.pk)

        self.assertEqual(retry.call_args.kwargs["countdown"], 30)
        self.assertNotIn(
            "result-secret-token",
            str(retry.call_args.kwargs["exc"]),
        )
        intent.refresh_from_db()
        self.assertIsNone(intent.notification_sent_at)

    @mock.patch("apps.payments.tasks.send_telegram_message")
    def test_historical_purchase_returns_before_transport(
        self,
        send: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="100006")
        payment = PaymentFactory(
            user=user,
            kind=PaymentKindEnum.SUBSCRIPTION,
            provider=PaymentProviderEnum.CRYPTO_PAY,
        )
        AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key=f"crypto_pay:{payment.charge_id}:subscription",
            rate_percent=None,
            apples_earned=0,
            balance_after=0,
            eligible_purchase_count_after=1,
            result_expired_at=None,
        )
        intent = CryptoPaymentIntentFactory(
            initiator=user,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            payment=payment,
        )

        notify_crypto_purchase_task.run(intent.pk)

        send.assert_not_called()
        intent.refresh_from_db()
        self.assertIsNone(intent.notification_sent_at)
