import json
from datetime import timedelta
from unittest import mock

import responses
from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import VDSInstanceFactory


class TestFirstFreeLink(APITestCase):
    url: str = reverse("first-free-link")

    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()

    def _mock_vds_request(self) -> None:
        responses.add(
            method=responses.POST,
            url=self.vds.internal_url + "/api/v2/users/add",
            json={
                "tls_domain": "petrovich.ru",
                "key": "test",
                "node_number": "telemt-node01",
            },
        )

    @responses.activate
    def test_first_free_link_30days(self) -> None:
        self._mock_vds_request()
        self.assertFalse(self.user.first_month_free_used)
        self.assertEqual(MTPRotoKey.objects.count(), 0)
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.user.refresh_from_db()
        self.assertTrue(self.user.first_month_free_used)
        self.assertFalse(self.user.referral_activated)
        self.assertEqual(MTPRotoKey.objects.first().vds, self.vds)
        self.assertEqual(
            MTPRotoKey.objects.first().expired_date.date(),
            (timezone.now() + timedelta(days=30)).date(),
        )

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            self.vds.internal_url + "/api/v2/users/add",
        )
        self.assertEqual(responses.calls[0].request.method, "POST")
        request_body = json.loads(responses.calls[0].request.body)
        self.assertEqual(request_body.get("username"), self.user.username)
        self.assertEqual(
            response.json(),
            {
                "link": MTPRotoKey.objects.first().get_proxy_link(),
                "expired_date": (timezone.now() + timedelta(days=30))
                .date()
                .strftime("%d.%m.%y"),
            },
        )

    @responses.activate
    def test_first_free_link_7days(self) -> None:
        for _ in range(50):
            SystemUserFactory(first_month_free_used=True)
        self._mock_vds_request()
        self.assertFalse(self.user.first_month_free_used)
        self.assertEqual(MTPRotoKey.objects.count(), 0)
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.user.refresh_from_db()
        self.assertTrue(self.user.first_month_free_used)
        self.assertFalse(self.user.referral_activated)
        self.assertEqual(MTPRotoKey.objects.first().vds, self.vds)
        self.assertEqual(
            MTPRotoKey.objects.first().expired_date.date(),
            (timezone.now() + timedelta(days=7)).date(),
        )
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            self.vds.internal_url + "/api/v2/users/add",
        )
        self.assertEqual(responses.calls[0].request.method, "POST")
        request_body = json.loads(responses.calls[0].request.body)
        self.assertEqual(request_body.get("username"), self.user.username)
        self.assertEqual(
            response.json(),
            {
                "link": MTPRotoKey.objects.first().get_proxy_link(),
                "expired_date": (timezone.now() + timedelta(days=7))
                .date()
                .strftime("%d.%m.%y"),
            },
        )

    @mock.patch("apps.core.bot.TelegramBot.log_service_error")
    def test_first_free_link_duplicate(self, service) -> None:
        self.user.first_month_free_used = True
        self.user.save(update_fields=["first_month_free_used"])

        self.assertEqual(MTPRotoKey.objects.count(), 0)
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MTPRotoKey.objects.count(), 0)
        self.user.refresh_from_db()
        self.assertTrue(self.user.first_month_free_used)
        self.assertEqual(len(responses.calls), 0)
        self.assertEqual(service.call_count, 1)

    @responses.activate
    def test_first_free_link_with_referral_14days(self) -> None:
        self._mock_vds_request()
        self.assertEqual(MTPRotoKey.objects.count(), 0)
        self.user.invited_from_username = "test"
        self.user.save()
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.user.refresh_from_db()
        self.assertTrue(self.user.first_month_free_used)
        self.assertTrue(self.user.referral_activated)
        self.assertEqual(MTPRotoKey.objects.first().vds, self.vds)
        self.assertEqual(
            MTPRotoKey.objects.first().expired_date.date(),
            (timezone.now() + timedelta(days=14)).date(),
        )

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            self.vds.internal_url + "/api/v2/users/add",
        )
        self.assertEqual(responses.calls[0].request.method, "POST")
        request_body = json.loads(responses.calls[0].request.body)
        self.assertEqual(request_body.get("username"), self.user.username)
        self.assertEqual(
            response.json(),
            {
                "link": MTPRotoKey.objects.first().get_proxy_link(),
                "expired_date": (timezone.now() + timedelta(days=14))
                .date()
                .strftime("%d.%m.%y"),
            },
        )


    def test_first_free_link_403(self) -> None:
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch("apps.core.bot.TelegramBot.log_bad_request")
    def test_first_free_link_400(self, log) -> None:
        response = self.client.post(
            path=self.url,
            data={},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
