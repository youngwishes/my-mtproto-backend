from __future__ import annotations

import re
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import PaymentProviderEnum, ProductCodeEnum
from apps.payments.exceptions import (
    GiftCertificateAlreadyActivated,
    GiftCertificateExpired,
    GiftCertificateNotFound,
)
from apps.payments.models import AppleCashbackPurchase, GiftCertificate, Payment
from apps.payments.services import (
    get_activate_gift_certificate_service,
    get_create_gift_certificate_service,
)
from apps.payments.services.dtos import (
    ActivateGiftCertificateIn,
    CreateGiftCertificateIn,
)
from apps.payments.tests.factories import GiftCertificateFactory, ProductFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestCreateGiftCertificateService(TestCase):
    def setUp(self) -> None:
        self.buyer = SystemUserFactory(username="111111")
        ProductFactory(
            code=ProductCodeEnum.MTPROTO_30D,
            price=9900,
            currency="RUB",
        )
        self.service = get_create_gift_certificate_service()

    def _make_certificate(
        self,
        *,
        username: str | None = None,
        charge_id: str = "gift_charge_1",
        provider: str = PaymentProviderEnum.YUKASSA,
    ) -> CreateGiftCertificateIn:
        return CreateGiftCertificateIn(
            username=username or self.buyer.username,
            charge_id=charge_id,
            provider=provider,
        )

    def test_creates_one_time_certificate_without_extending_buyer_key(self) -> None:
        original_expired = timezone.now() + timedelta(days=12)
        key = MTPRotoKeyFactory(user=self.buyer, expired_date=original_expired)

        result = self.service(certificate=self._make_certificate())

        key.refresh_from_db()
        self.assertEqual(key.expired_date, original_expired)
        self.assertEqual(MTPRotoKey.objects.count(), 1)

        certificate = GiftCertificate.objects.get()
        self.assertEqual(result.code, certificate.code)
        self.assertRegex(certificate.code, r"^KEY-[A-Z0-9]{4}-[A-Z0-9]{4}$")
        self.assertEqual(certificate.buyer, self.buyer)
        self.assertIsNone(certificate.activated_by)
        self.assertIsNone(certificate.activated_at)
        self.assertEqual(certificate.status, GiftCertificate.Status.CREATED)
        self.assertAlmostEqual(
            certificate.expires_at,
            timezone.now() + timedelta(days=365),
            delta=timedelta(seconds=5),
        )

        payment = Payment.objects.get()
        self.assertIsNone(payment.key)
        self.assertEqual(payment.user, self.buyer)
        self.assertEqual(payment.charge_id, "gift_charge_1")
        self.assertEqual(payment.provider, PaymentProviderEnum.YUKASSA)
        self.assertEqual(payment.kind, Payment.Kind.GIFT_CERTIFICATE)
        self.assertEqual(certificate.payment, payment)
        self.assertEqual(result.loyalty.apples_earned, 5)
        self.assertEqual(result.loyalty.balance, 5)

    def test_supports_stars_certificate_payment(self) -> None:
        self.service(certificate=self._make_certificate(
            charge_id="stars_gift_tx",
            provider=PaymentProviderEnum.STARS,
        ))

        payment = Payment.objects.get()
        self.assertEqual(payment.charge_id, "stars_gift_tx")
        self.assertEqual(payment.provider, PaymentProviderEnum.STARS)
        self.assertEqual(payment.kind, Payment.Kind.GIFT_CERTIFICATE)

    def test_repeated_payment_confirmation_returns_existing_certificate(self) -> None:
        first = self.service(certificate=self._make_certificate(charge_id="same_charge"))
        second = self.service(certificate=self._make_certificate(charge_id="same_charge"))

        self.assertEqual(second.code, first.code)
        self.assertEqual(second.loyalty, first.loyalty)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(GiftCertificate.objects.count(), 1)

    @mock.patch("apps.payments.services.gift_certificates.secrets.choice")
    def test_retries_code_generation_on_collision(self, mock_choice: mock.Mock) -> None:
        GiftCertificateFactory(code="KEY-AAAA-AAAA")
        mock_choice.side_effect = list("AAAAAAAA") + list("BBBBBBBB")

        result = self.service(certificate=self._make_certificate())

        self.assertEqual(result.code, "KEY-BBBB-BBBB")
        self.assertEqual(GiftCertificate.objects.count(), 2)


class TestActivateGiftCertificateService(TestCase):
    def setUp(self) -> None:
        self.recipient = SystemUserFactory(
            username="222222",
            first_month_free_used=False,
            referral_activated=False,
        )
        self.service = get_activate_gift_certificate_service()

    def _activate(
        self,
        *,
        username: str | None = None,
        code: str = "KEY-TEST-1234",
    ) -> ActivateGiftCertificateIn:
        return ActivateGiftCertificateIn(
            username=username or self.recipient.username,
            code=code,
        )

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_activates_new_key_without_touching_free_or_referral_state(
        self, mock_push: mock.Mock
    ) -> None:
        certificate = GiftCertificateFactory(code="KEY-TEST-1234")

        with self.captureOnCommitCallbacks(execute=True):
            result = self.service(activation=self._activate())

        self.recipient.refresh_from_db()
        key = MTPRotoKey.objects.get(user=self.recipient)
        self.assertAlmostEqual(
            key.expired_date,
            timezone.now() + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )
        self.assertEqual(result.expired_date, key.expired_date.date().strftime("%d.%m.%y"))
        self.assertFalse(self.recipient.first_month_free_used)
        self.assertFalse(self.recipient.referral_activated)
        self.assertEqual(self.recipient.apple_balance, 0)
        self.assertFalse(
            AppleCashbackPurchase.objects.filter(
                payment__user=self.recipient
            ).exists()
        )
        mock_push.assert_called_once_with(key_id=key.pk)

        certificate.refresh_from_db()
        self.assertEqual(certificate.status, GiftCertificate.Status.ACTIVATED)
        self.assertEqual(certificate.activated_by, self.recipient)
        self.assertIsNotNone(certificate.activated_at)

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_new_key_push_is_deferred_until_activation_transaction_commits(
        self, mock_push: mock.Mock
    ) -> None:
        GiftCertificateFactory(code="KEY-TEST-1234")

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.service(activation=self._activate())
            mock_push.assert_not_called()

        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        mock_push.assert_called_once()

    def test_extends_existing_active_key(self) -> None:
        original_expired = timezone.now() + timedelta(days=8)
        key = MTPRotoKeyFactory(user=self.recipient, expired_date=original_expired)
        certificate = GiftCertificateFactory(code="KEY-TEST-1234")

        result = self.service(activation=self._activate())

        key.refresh_from_db()
        self.assertAlmostEqual(
            key.expired_date,
            original_expired + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )
        self.assertEqual(result.expired_date, key.expired_date.date().strftime("%d.%m.%y"))
        certificate.refresh_from_db()
        self.assertEqual(certificate.activated_by, self.recipient)

    def test_rejects_used_certificate(self) -> None:
        GiftCertificateFactory(
            code="KEY-TEST-1234",
            status=GiftCertificate.Status.ACTIVATED,
            activated_by=SystemUserFactory(username="333333"),
            activated_at=timezone.now(),
        )

        with self.assertRaises(GiftCertificateAlreadyActivated):
            self.service(activation=self._activate())

    def test_rejects_expired_certificate_and_marks_it_expired(self) -> None:
        certificate = GiftCertificateFactory(
            code="KEY-TEST-1234",
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        with self.assertRaises(GiftCertificateExpired):
            self.service(activation=self._activate())

        certificate.refresh_from_db()
        self.assertEqual(certificate.status, GiftCertificate.Status.EXPIRED)

    def test_rejects_unknown_certificate(self) -> None:
        with self.assertRaises(GiftCertificateNotFound):
            self.service(activation=self._activate(code="KEY-NONE-0000"))

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_rejects_when_certificate_reservation_loses_race(
        self, mock_push: mock.Mock
    ) -> None:
        certificate = GiftCertificateFactory(code="KEY-TEST-1234")

        with mock.patch(
            "apps.payments.services.gift_certificates.GiftCertificate.objects"
        ) as gift_certificate_manager:
            gift_certificate_manager.filter.return_value.select_related.return_value.first.return_value = certificate
            gift_certificate_manager.filter.return_value.update.return_value = 0

            with self.assertRaises(GiftCertificateAlreadyActivated):
                self.service(activation=self._activate())

        self.assertEqual(MTPRotoKey.objects.count(), 0)
        mock_push.assert_not_called()

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_code_normalization_accepts_lowercase_and_spaces(
        self, mock_push: mock.Mock
    ) -> None:
        GiftCertificateFactory(code="KEY-ABCD-1234")

        with self.captureOnCommitCallbacks(execute=True):
            result = self.service(
                activation=self._activate(code=" key-abcd-1234 "),
            )

        self.assertTrue(re.match(r"\d{2}\.\d{2}\.\d{2}", result.expired_date))
        mock_push.assert_called_once()
