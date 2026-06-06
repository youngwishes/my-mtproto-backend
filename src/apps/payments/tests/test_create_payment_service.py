from __future__ import annotations

from datetime import timedelta
from unittest import mock

import responses
from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import PaymentProviderEnum
from apps.payments.exceptions import BadPaymentData
from apps.payments.models import Payment
from apps.payments.services import get_create_payment_service
from apps.payments.services.dtos import CreatePaymentIn
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestCreatePaymentService(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory(username="12345678")
        self.vds = VDSInstanceFactory()
        self.service = get_create_payment_service()

    def _make_payment(
        self,
        *,
        username: str | None = None,
        charge_id: str = "charge_1",
        provider: str = PaymentProviderEnum.YUKASSA,
    ) -> CreatePaymentIn:
        return CreatePaymentIn(
            username=username or self.user.username,
            charge_id=charge_id,
            provider=provider,
        )

    def _mock_vds_request(self) -> None:
        responses.add(
            method=responses.POST,
            url=self.vds.internal_url + "/api/users",
            json={
                "tls_domain": "petrovich.ru",
                "key": "testtoken123",
            },
        )

    @responses.activate
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @mock.patch("apps.notifications.services.send_notification_service.send")
    def test_creates_new_key_when_no_active_key(self, mock_send: mock.Mock, _task: mock.Mock) -> None:
        self._mock_vds_request()

        self.service(payment=self._make_payment(charge_id="charge_new"))

        self.assertEqual(MTPRotoKey.objects.count(), 1)
        key = MTPRotoKey.objects.first()
        self.assertEqual(key.user, self.user)
        self.assertEqual(key.tls_domain, "petrovich.ru")
        self.assertAlmostEqual(
            key.expired_date,
            timezone.now() + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )

        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.first()
        self.assertEqual(payment.key, key)
        self.assertEqual(payment.charge_id, "charge_new")
        self.assertEqual(payment.provider, PaymentProviderEnum.YUKASSA)

        mock_send.assert_called_once()

    @mock.patch("apps.notifications.services.send_notification_service.send")
    def test_extends_existing_active_key(self, mock_send: mock.Mock) -> None:
        existing_key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=15),
            was_deleted=False,
        )
        original_expired = existing_key.expired_date

        self.service(payment=self._make_payment(charge_id="charge_extend"))

        existing_key.refresh_from_db()
        self.assertAlmostEqual(
            existing_key.expired_date,
            original_expired + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )

        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.first()
        self.assertEqual(payment.key, existing_key)
        self.assertEqual(payment.charge_id, "charge_extend")

        mock_send.assert_called_once()

    @responses.activate
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @mock.patch("apps.notifications.services.send_notification_service.send")
    def test_creates_new_key_when_existing_key_is_expired(self, mock_send: mock.Mock, _task: mock.Mock) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() - timedelta(days=1),
            was_deleted=False,
        )
        self._mock_vds_request()

        self.service(payment=self._make_payment(charge_id="charge_expired"))

        self.assertEqual(MTPRotoKey.objects.count(), 1)
        new_key = MTPRotoKey.objects.first()
        self.assertAlmostEqual(
            new_key.expired_date,
            timezone.now() + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )
        self.assertEqual(Payment.objects.first().key, new_key)

    @responses.activate
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @mock.patch("apps.notifications.services.send_notification_service.send")
    def test_creates_new_key_when_existing_key_was_deleted(self, mock_send: mock.Mock, _task: mock.Mock) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=True,
        )
        self._mock_vds_request()

        self.service(payment=self._make_payment(charge_id="charge_deleted"))

        self.assertEqual(MTPRotoKey.objects.count(), 1)
        new_key = MTPRotoKey.objects.first()
        self.assertFalse(new_key.was_deleted)
        self.assertEqual(Payment.objects.first().key, new_key)

    @responses.activate
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @mock.patch("apps.notifications.services.send_notification_service.send")
    def test_stars_payment_issues_new_key(self, mock_send: mock.Mock, _task: mock.Mock) -> None:
        self._mock_vds_request()

        self.service(payment=self._make_payment(
            charge_id="stars_tx_123",
            provider=PaymentProviderEnum.STARS,
        ))

        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.first()
        self.assertEqual(payment.charge_id, "stars_tx_123")
        self.assertEqual(payment.provider, PaymentProviderEnum.STARS)

    @mock.patch("apps.notifications.services.send_notification_service.send")
    def test_stars_payment_extends_existing_key(self, mock_send: mock.Mock) -> None:
        existing_key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=15),
            was_deleted=False,
        )
        original_expired = existing_key.expired_date

        self.service(payment=self._make_payment(
            charge_id="stars_tx_456",
            provider=PaymentProviderEnum.STARS,
        ))

        existing_key.refresh_from_db()
        self.assertAlmostEqual(
            existing_key.expired_date,
            original_expired + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )

        payment = Payment.objects.first()
        self.assertEqual(payment.charge_id, "stars_tx_456")
        self.assertEqual(payment.provider, PaymentProviderEnum.STARS)

    @mock.patch("apps.core.service._log_service_error")
    def test_raises_bad_payment_data_when_user_not_found(self, mock_log: mock.Mock) -> None:
        with self.assertRaises(BadPaymentData):
            self.service(payment=self._make_payment(username="nonexistent_user"))

        self.assertEqual(Payment.objects.count(), 0)
        mock_log.assert_called_once()
