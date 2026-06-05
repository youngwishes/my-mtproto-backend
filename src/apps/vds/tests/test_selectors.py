from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.selectors import get_active_key
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestGetActiveKey(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()

    def test_returns_active_key(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
        )
        result = get_active_key(user=self.user)
        self.assertEqual(result, key)

    def test_returns_none_when_no_key(self) -> None:
        result = get_active_key(user=self.user)
        self.assertIsNone(result)

    def test_returns_none_when_key_expired(self) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() - timedelta(days=1),
            was_deleted=False,
        )
        result = get_active_key(user=self.user)
        self.assertIsNone(result)

    def test_returns_none_when_key_deleted(self) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=True,
        )
        result = get_active_key(user=self.user)
        self.assertIsNone(result)
