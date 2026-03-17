import responses
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory
from datetime import datetime
from unittest import mock

class TestUpdateKeyView(APITestCase):
    url: str = reverse("update-link")

    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.server = VDSInstanceFactory()

    def _mock_vds_request(self) -> None:
        responses.add(
            method=responses.POST,
            url=self.server.internal_url + "/api/v1/add-new-user",
            json={
                "tls_domain": "petrovich.ru",
                "key": "test2",
                "node_number": "node2",
            },
        )

    @responses.activate
    def test_update_user_key(self) -> None:
        self._mock_vds_request()
        user_key_before = MTPRotoKeyFactory(
            user=self.user,
            vds=self.server,
            tls_domain="dzen.ru",
            node_number="node1",
            token="test1",
            expired_date=datetime.now(),
        )
        response = self.client.post(
            path=self.url,
            data={
                "username": self.user.username,
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(MTPRotoKey.objects.filter(user=self.user).count(), 1)

        user_key_after = MTPRotoKey.objects.first()

        self.assertEqual(user_key_after.tls_domain, "petrovich.ru")
        self.assertEqual(user_key_after.node_number, "node2")
        self.assertEqual(user_key_after.token, "test2")

        self.assertEqual(user_key_after.expired_date.date(), user_key_before.expired_date.date())
        self.assertNotEqual(user_key_before.get_proxy_link(), user_key_after.get_proxy_link())

        self.assertEqual(
            response.json(),
            {
                "link": user_key_after.get_proxy_link(),
                "expired_date": user_key_after.expired_date.strftime("%d.%m.%y"),
            }
        )

    @responses.activate
    @mock.patch("apps.core.bot.TelegramBot.log_service_error")
    def test_update_user_key_if_not_active(self, service) -> None:
        self._mock_vds_request()
        user_key_before = MTPRotoKeyFactory(
            user=self.user,
            vds=self.server,
            tls_domain="dzen.ru",
            node_number="node1",
            token="test1",
            expired_date=datetime.now(),
            is_active=False,
        )
        response = self.client.post(
            path=self.url,
            data={
                "username": self.user.username,
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MTPRotoKey.objects.filter(user=self.user).count(), 1)

        user_key_before.refresh_from_db()
        self.assertEqual(user_key_before.tls_domain, "dzen.ru")
        self.assertEqual(user_key_before.node_number, "node1")
        self.assertEqual(user_key_before.token, "test1")
        self.assertEqual(service.call_count, 1)

    @responses.activate
    @mock.patch("apps.core.bot.TelegramBot.log_service_error")
    def test_update_user_key_if_was_deleted(self, service) -> None:
        self._mock_vds_request()
        user_key_before = MTPRotoKeyFactory(
            user=self.user,
            vds=self.server,
            tls_domain="dzen.ru",
            node_number="node1",
            token="test1",
            expired_date=datetime.now(),
            was_deleted=True,
        )
        response = self.client.post(
            path=self.url,
            data={
                "username": self.user.username,
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MTPRotoKey.objects.filter(user=self.user).count(), 1)

        user_key_before.refresh_from_db()
        self.assertEqual(user_key_before.tls_domain, "dzen.ru")
        self.assertEqual(user_key_before.node_number, "node1")
        self.assertEqual(user_key_before.token, "test1")
        self.assertEqual(service.call_count, 1)

    @responses.activate
    @mock.patch("apps.core.bot.TelegramBot.log_service_error")
    def test_update_user_key_if_not_exist(self, service) -> None:
        self._mock_vds_request()
        response = self.client.post(
            path=self.url,
            data={
                "username": self.user.username,
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MTPRotoKey.objects.filter(user=self.user).count(), 0)
