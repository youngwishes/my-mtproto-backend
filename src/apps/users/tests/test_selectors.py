from __future__ import annotations

from django.test import TestCase

from apps.users.selectors import get_user_by_username
from apps.users.tests.factories import SystemUserFactory


class TestGetUserByUsername(TestCase):
    def test_returns_user_when_exists(self) -> None:
        user = SystemUserFactory(username="123456")
        result = get_user_by_username(username="123456")
        self.assertEqual(result, user)

    def test_returns_none_when_not_found(self) -> None:
        result = get_user_by_username(username="nonexistent")
        self.assertIsNone(result)
