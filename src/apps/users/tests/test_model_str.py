from __future__ import annotations

from django.test import TestCase

from apps.users.models import SystemUser
from apps.users.tests.factories import SystemUserFactory

DASH = "-"


class TestSystemUserStr(TestCase):
    def test_real_username_is_shown(self) -> None:
        user = SystemUserFactory(telegram_username="@durov")
        self.assertEqual(str(user), "@durov")

    def test_empty_username_becomes_dash(self) -> None:
        user = SystemUserFactory(telegram_username="")
        self.assertEqual(str(user), DASH)

    def test_none_username_becomes_dash(self) -> None:
        user = SystemUser(username="123", telegram_username=None)
        self.assertEqual(str(user), DASH)
