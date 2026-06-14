from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.exceptions import KeysLimitReached
from apps.vds.models import MTPRotoKey
from apps.vds.services import get_issue_key_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestIssueKeyService(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.expired_date = timezone.now() + timedelta(days=30)

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_creates_key_as_pure_db_write_without_server(self, mock_delay) -> None:
        # Нет ни одного VDS — выдача всё равно проходит (чистая запись в БД).
        self.assertEqual(MTPRotoKey.objects.count(), 0)

        key = get_issue_key_service()(user=self.user, expired_date=self.expired_date)

        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertEqual(key.user, self.user)
        self.assertIsNone(key.vds_id)
        self.assertTrue(key.token)
        self.assertEqual(key.expired_date, self.expired_date)

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_generates_random_hex_token(self, mock_delay) -> None:
        key = get_issue_key_service()(user=self.user, expired_date=self.expired_date)

        self.assertEqual(len(key.token), 32)  # 16 random bytes → 32 hex chars
        int(key.token, 16)  # raises if not valid hex

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_schedules_push_to_servers_task(self, mock_delay) -> None:
        key = get_issue_key_service()(user=self.user, expired_date=self.expired_date)

        mock_delay.assert_called_once_with(key_id=key.pk)

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_deletes_prior_keys_of_same_user(self, mock_delay) -> None:
        old_key = MTPRotoKeyFactory(
            user=self.user,
            expired_date=timezone.now() - timedelta(days=1),
        )
        other_user_key = MTPRotoKeyFactory(expired_date=timezone.now() + timedelta(days=5))

        new_key = get_issue_key_service()(user=self.user, expired_date=self.expired_date)

        self.assertFalse(MTPRotoKey.objects.filter(pk=old_key.pk).exists())
        self.assertEqual(
            list(MTPRotoKey.objects.filter(user=self.user).values_list("pk", flat=True)),
            [new_key.pk],
        )
        # ключи других пользователей не трогаем
        self.assertTrue(MTPRotoKey.objects.filter(pk=other_user_key.pk).exists())

    @override_settings(GLOBAL_KEYS_LIMIT=1)
    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_raises_when_global_limit_reached(self, mock_delay) -> None:
        MTPRotoKeyFactory(
            vds=VDSInstanceFactory(),
            is_active=True,
            was_deleted=False,
            expired_date=timezone.now() + timedelta(days=30),
        )

        with self.assertRaises(KeysLimitReached):
            get_issue_key_service()(user=self.user, expired_date=self.expired_date)

        self.assertEqual(MTPRotoKey.objects.filter(user=self.user).count(), 0)
        mock_delay.assert_not_called()
