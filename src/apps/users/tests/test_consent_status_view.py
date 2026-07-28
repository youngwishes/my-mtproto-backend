from __future__ import annotations

from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import SystemUser
from apps.users.tests.factories import SystemUserFactory


class TestLegalConsentStatusView(APITestCase):
    url = "/api/v1/users/consent/status/"
    headers = {"Bot-Auth-Token": settings.BOT_AUTH_TOKEN}

    def test_missing_user_returns_false_without_database_write(self) -> None:
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                self.url,
                {"username": "123456"},
                format="json",
                headers=self.headers,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"legal_terms_accepted": False})
        self.assertFalse(SystemUser.objects.filter(username="123456").exists())
        mutating_queries = [
            query["sql"]
            for query in queries.captured_queries
            if query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]
        self.assertEqual(mutating_queries, [])

    def test_returns_saved_status_without_updating_user(self) -> None:
        user = SystemUserFactory(
            username="123457",
            telegram_username="unchanged",
            legal_terms_accepted=True,
        )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                self.url,
                {"username": user.username},
                format="json",
                headers=self.headers,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"legal_terms_accepted": True})
        user.refresh_from_db()
        self.assertEqual(user.telegram_username, "unchanged")
        mutating_queries = [
            query["sql"]
            for query in queries.captured_queries
            if query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]
        self.assertEqual(mutating_queries, [])

    def test_rejects_non_numeric_username(self) -> None:
        response = self.client.post(
            self.url,
            {"username": "not-a-telegram-id"},
            format="json",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SystemUser.objects.count(), 0)

    def test_rejects_non_string_username(self) -> None:
        response = self.client.post(
            self.url,
            {"username": 123456},
            format="json",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SystemUser.objects.count(), 0)

    def test_rejects_username_with_surrounding_whitespace(self) -> None:
        for username in (" 123458", "123459 "):
            with self.subTest(username=username):
                response = self.client.post(
                    self.url,
                    {"username": username},
                    format="json",
                    headers=self.headers,
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )
        self.assertEqual(SystemUser.objects.count(), 0)

    def test_requires_bot_auth_token(self) -> None:
        response = self.client.post(
            self.url,
            {"username": "123456"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
