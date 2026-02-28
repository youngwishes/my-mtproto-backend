import json

import responses
from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import VDSInstanceFactory


class TestFirstMonthFree(APITestCase):
    url: str = reverse("first-month-free")

    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()

    def _mock_vds_request(self) -> None:
        responses.add(
            method=responses.POST,
            url=self.vds.internal_url + "/api/v1/add-new-user",
            json={"tls_domain": "petrovich.ru", "key": "test"},
        )

    @responses.activate
    def test_first_month_free(self) -> None:
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
        self.assertEqual(MTPRotoKey.objects.first().vds, self.vds)
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            self.vds.internal_url + "/api/v1/add-new-user",
        )
        self.assertEqual(responses.calls[0].request.method, "POST")
        request_body = json.loads(responses.calls[0].request.body)
        self.assertEqual(request_body.get("username"), self.user.username)
        self.assertEqual(
            response.json(), {"link": MTPRotoKey.objects.first().get_proxy_link()}
        )

    def test_first_month_free_duplicate(self) -> None:
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

    def test_first_month_free_403(self) -> None:
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_first_month_free_400(self) -> None:
        response = self.client.post(
            path=self.url,
            data={},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
