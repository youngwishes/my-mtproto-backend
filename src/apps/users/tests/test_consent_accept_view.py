from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import mock

from django.conf import settings
from django.db import close_old_connections
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.users.models import SystemUser
from apps.users.tests.factories import SystemUserFactory


class TestLegalConsentAcceptView(APITestCase):
    url = "/api/v1/users/consent/accept/"
    headers = {"Bot-Auth-Token": settings.BOT_AUTH_TOKEN}

    def test_creates_exactly_one_accepted_user(self) -> None:
        response = self.client.post(
            self.url,
            {
                "username": "200001",
                "telegram_username": "new_user",
            },
            format="json",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"legal_terms_accepted": True})
        user = SystemUser.objects.get(username="200001")
        self.assertTrue(user.legal_terms_accepted)
        self.assertEqual(user.telegram_username, "new_user")
        self.assertEqual(SystemUser.objects.filter(username="200001").count(), 1)

    def test_saves_valid_referrer_only_during_accept(self) -> None:
        self.assertFalse(SystemUser.objects.filter(username="200002").exists())

        response = self.client.post(
            self.url,
            {
                "username": "200002",
                "telegram_username": "referred_user",
                "invited_from_username": "100001",
            },
            format="json",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user = SystemUser.objects.get(username="200002")
        self.assertEqual(user.invited_from_username, "100001")
        self.assertTrue(user.legal_terms_accepted)

    def test_rejects_non_numeric_username(self) -> None:
        response = self.client.post(
            self.url,
            {"username": "not-numeric"},
            format="json",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SystemUser.objects.count(), 0)

    def test_rejects_non_string_username(self) -> None:
        response = self.client.post(
            self.url,
            {"username": 200003},
            format="json",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SystemUser.objects.count(), 0)

    def test_rejects_username_with_surrounding_whitespace_without_write(
        self,
    ) -> None:
        for username in (" 200011", "200012 "):
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

    def test_rejects_non_numeric_referrer(self) -> None:
        response = self.client.post(
            self.url,
            {
                "username": "200004",
                "invited_from_username": "not-numeric",
            },
            format="json",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(SystemUser.objects.filter(username="200004").exists())

    def test_rejects_referrer_with_surrounding_whitespace_without_write(
        self,
    ) -> None:
        for username, invited_from_username in (
            ("200013", " 100008"),
            ("200014", "100009 "),
        ):
            with self.subTest(invited_from_username=invited_from_username):
                response = self.client.post(
                    self.url,
                    {
                        "username": username,
                        "invited_from_username": invited_from_username,
                    },
                    format="json",
                    headers=self.headers,
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )
        self.assertEqual(SystemUser.objects.count(), 0)

    def test_rejects_self_referrer(self) -> None:
        response = self.client.post(
            self.url,
            {
                "username": "200005",
                "invited_from_username": "00200005",
            },
            format="json",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(SystemUser.objects.filter(username="200005").exists())

    def test_repeated_accept_does_not_duplicate_user_or_change_referrer(self) -> None:
        first = self.client.post(
            self.url,
            {
                "username": "200006",
                "telegram_username": "original",
                "invited_from_username": "100002",
            },
            format="json",
            headers=self.headers,
        )
        second = self.client.post(
            self.url,
            {
                "username": "200006",
                "telegram_username": "replacement",
                "invited_from_username": "100003",
            },
            format="json",
            headers=self.headers,
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.json(), {"legal_terms_accepted": True})
        self.assertEqual(SystemUser.objects.filter(username="200006").count(), 1)
        user = SystemUser.objects.get(username="200006")
        self.assertEqual(user.invited_from_username, "100002")
        self.assertEqual(user.telegram_username, "original")

    def test_existing_unaccepted_user_becomes_accepted_without_referrer_change(
        self,
    ) -> None:
        user = SystemUserFactory(
            username="200007",
            telegram_username="existing",
            invited_from_username="100004",
            legal_terms_accepted=False,
        )

        response = self.client.post(
            self.url,
            {
                "username": user.username,
                "telegram_username": "replacement",
                "invited_from_username": "100005",
            },
            format="json",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"legal_terms_accepted": True})
        user.refresh_from_db()
        self.assertTrue(user.legal_terms_accepted)
        self.assertEqual(user.invited_from_username, "100004")
        self.assertEqual(user.telegram_username, "existing")

    def test_failure_inside_accept_rolls_back_new_user(self) -> None:
        from apps.users.selectors import accept_legal_terms
        from apps.users.services import AcceptLegalConsentService
        from apps.users.services.dtos import AcceptLegalConsentIn

        def accept_then_fail(**kwargs):
            accept_legal_terms(**kwargs)
            raise RuntimeError("forced failure")

        service = AcceptLegalConsentService(accept_user=accept_then_fail)

        with self.assertRaisesMessage(RuntimeError, "forced failure"):
            service(data=AcceptLegalConsentIn(username="200008"))

        self.assertFalse(SystemUser.objects.filter(username="200008").exists())

    def test_requires_bot_auth_token(self) -> None:
        response = self.client.post(
            self.url,
            {"username": "200009"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TestConcurrentLegalConsentAccept(TransactionTestCase):
    url = "/api/v1/users/consent/accept/"
    headers = {"Bot-Auth-Token": settings.BOT_AUTH_TOKEN}

    def test_two_concurrent_accepts_create_one_consistently_accepted_user(
        self,
    ) -> None:
        barrier = Barrier(2)

        def accept(invited_from_username: str) -> tuple[int, dict]:
            close_old_connections()
            client = APIClient()
            barrier.wait()
            try:
                response = client.post(
                    self.url,
                    {
                        "username": "200010",
                        "telegram_username": "concurrent",
                        "invited_from_username": invited_from_username,
                    },
                    format="json",
                    headers=self.headers,
                )
                return response.status_code, response.json()
            finally:
                close_old_connections()

        with mock.patch("apps.core.decorators._log_service_error"):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(
                    executor.map(
                        accept,
                        ("100006", "100007"),
                    )
                )

        self.assertEqual(
            results,
            [
                (status.HTTP_200_OK, {"legal_terms_accepted": True}),
                (status.HTTP_200_OK, {"legal_terms_accepted": True}),
            ],
        )
        self.assertEqual(SystemUser.objects.filter(username="200010").count(), 1)
        self.assertTrue(
            SystemUser.objects.get(username="200010").legal_terms_accepted
        )
