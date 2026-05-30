from __future__ import annotations

import json
from datetime import timedelta
from unittest import mock

import responses
from django.test import TestCase
from django.utils import timezone

from apps.payments.models import Payment
from apps.payments.services import get_create_payment_service
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestCreatePaymentService(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()
        self.service = get_create_payment_service()

    def _mock_vds_request(self) -> None:
        responses.add(
            method=responses.POST,
            url=self.vds.internal_url + "/api/v2/users/add",
            json={
                "tls_domain": "petrovich.ru",
                "key": "testtoken123",
                "node_number": "telemt-node01",
            },
        )

    @responses.activate
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    def test_creates_new_key_when_no_active_key(self, mock_send: mock.Mock, _task: mock.Mock) -> None:
        self._mock_vds_request()

        self.service(username=self.user.username, provider_payment_charge_id="charge_new")

        self.assertEqual(MTPRotoKey.objects.count(), 1)
        key = MTPRotoKey.objects.first()
        self.assertEqual(key.user, self.user)
        self.assertEqual(key.tls_domain, "petrovich.ru")
        self.assertAlmostEqual(
            key.expired_date,
            timezone.now() + timedelta(days=30),
            delta=timedelta(seconds=5),
        )

        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.first()
        self.assertEqual(payment.key, key)
        self.assertEqual(payment.provider_payment_charge_id, "charge_new")

        mock_send.assert_called_once_with(
            chat_id=self.user.username,
            link=key.get_proxy_link(),
        )
        self.assertEqual(len(responses.calls), 1)
        body = json.loads(responses.calls[0].request.body)
        self.assertEqual(body["username"], self.user.username)

    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    def test_extends_existing_active_key(self, mock_send: mock.Mock) -> None:
        existing_key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=15),
            was_deleted=False,
            payment=None,
        )
        original_expired = existing_key.expired_date

        self.service(username=self.user.username, provider_payment_charge_id="charge_extend")

        existing_key.refresh_from_db()
        self.assertAlmostEqual(
            existing_key.expired_date,
            original_expired + timedelta(days=30),
            delta=timedelta(seconds=5),
        )

        # No new key was issued
        self.assertEqual(MTPRotoKey.objects.count(), 1)

        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.first()
        self.assertEqual(payment.key, existing_key)
        self.assertEqual(payment.provider_payment_charge_id, "charge_extend")

        mock_send.assert_called_once_with(
            chat_id=self.user.username,
            link=existing_key.get_proxy_link(),
        )

    @responses.activate
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    def test_creates_new_key_when_existing_key_is_expired(self, mock_send: mock.Mock, _task: mock.Mock) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() - timedelta(days=1),
            was_deleted=False,
            payment=None,
        )
        self._mock_vds_request()

        self.service(username=self.user.username, provider_payment_charge_id="charge_expired")

        # AddNewKeyInfraService deletes all previous user keys before creating a new one
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        new_key = MTPRotoKey.objects.first()
        self.assertAlmostEqual(
            new_key.expired_date,
            timezone.now() + timedelta(days=30),
            delta=timedelta(seconds=5),
        )
        self.assertEqual(Payment.objects.first().key, new_key)

    @responses.activate
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    def test_creates_new_key_when_existing_key_was_deleted(self, mock_send: mock.Mock, _task: mock.Mock) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=True,
            payment=None,
        )
        self._mock_vds_request()

        self.service(username=self.user.username, provider_payment_charge_id="charge_deleted")

        # AddNewKeyInfraService deletes all previous user keys before creating a new one
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        new_key = MTPRotoKey.objects.first()
        self.assertFalse(new_key.was_deleted)
        self.assertEqual(Payment.objects.first().key, new_key)
