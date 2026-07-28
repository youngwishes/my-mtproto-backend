from __future__ import annotations

from importlib import import_module

from django.apps import apps as django_apps
from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import SystemUser
from apps.users.tests.factories import SystemUserFactory


class TestLegalConsent(APITestCase):
    def setUp(self) -> None:
        self.headers = {"Bot-Auth-Token": settings.BOT_AUTH_TOKEN}

    def test_status_for_missing_user_is_false_and_does_not_create_user(self) -> None:
        response = self.client.post(
            reverse("legal-consent-status"),
            data={"username": "100001"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"legal_terms_accepted": False})
        self.assertFalse(SystemUser.objects.filter(username="100001").exists())

    def test_status_returns_saved_value(self) -> None:
        SystemUserFactory(username="100002", legal_terms_accepted=True)

        response = self.client.post(
            reverse("legal-consent-status"),
            data={"username": "100002"},
            headers=self.headers,
        )

        self.assertEqual(response.json(), {"legal_terms_accepted": True})

    def test_accept_creates_accepted_user_with_telegram_data(self) -> None:
        response = self.client.post(
            reverse("legal-consent-accept"),
            data={
                "username": "100003",
                "telegram_username": "alice",
                "invited_from_username": "900001",
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"legal_terms_accepted": True})
        user = SystemUser.objects.get(username="100003")
        self.assertTrue(user.legal_terms_accepted)
        self.assertEqual(user.telegram_username, "alice")
        self.assertEqual(user.invited_from_username, "900001")

    def test_repeated_accept_does_not_overwrite_referrer(self) -> None:
        user = SystemUserFactory(
            username="100004",
            invited_from_username="900001",
            legal_terms_accepted=True,
        )

        response = self.client.post(
            reverse("legal-consent-accept"),
            data={
                "username": user.username,
                "telegram_username": "replacement",
                "invited_from_username": "900002",
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.invited_from_username, "900001")

    def test_new_user_defaults_to_not_accepted(self) -> None:
        user = SystemUserFactory(username="100005")

        self.assertFalse(user.legal_terms_accepted)

    def test_migration_marks_existing_users_as_accepted(self) -> None:
        user = SystemUserFactory(username="100006")
        migration = import_module(
            "apps.users.migrations.0017_systemuser_legal_terms_accepted"
        )

        migration.accept_existing_users(django_apps, None)

        user.refresh_from_db()
        self.assertTrue(user.legal_terms_accepted)
