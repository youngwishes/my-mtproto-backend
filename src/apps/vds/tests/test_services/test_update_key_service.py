from __future__ import annotations

from datetime import timedelta
from unittest import mock

import responses
from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.exceptions import KeyDoesNotExist, TooManyRequests
from apps.vds.models import MTPRotoKey
from apps.vds.services import get_update_key_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


@mock.patch("apps.core.decorators._log_service_error")
@mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
class TestUpdateKeyService(TestCase):
    def setUp(self) -> None:
        self.future = timezone.now() + timedelta(days=30)

    def test_generates_new_token_and_keeps_active_record(self, mock_delay, mock_log) -> None:
        key = MTPRotoKeyFactory(token="old-token", expired_date=self.future)

        get_update_key_service()(username=str(key.user.username))

        key.refresh_from_db()
        self.assertNotEqual(key.token, "old-token")
        self.assertEqual(len(key.token), 32)  # 16 random bytes → 32 hex chars
        self.assertTrue(key.is_active)
        self.assertFalse(key.was_deleted)
        self.assertIsNotNone(key.last_update)

    def test_schedules_push_to_servers_task(self, mock_delay, mock_log) -> None:
        key = MTPRotoKeyFactory(expired_date=self.future)

        get_update_key_service()(username=str(key.user.username))

        key.refresh_from_db()
        mock_delay.assert_called_once_with(key_id=key.pk)

    def test_deletes_other_keys_of_user(self, mock_delay, mock_log) -> None:
        user = SystemUserFactory()
        MTPRotoKeyFactory(user=user, expired_date=self.future)
        MTPRotoKeyFactory(user=user, expired_date=self.future)

        get_update_key_service()(username=str(user.username))

        self.assertEqual(MTPRotoKey.objects.filter(user=user).count(), 1)

    @responses.activate
    def test_makes_no_synchronous_http_calls(self, mock_delay, mock_log) -> None:
        # Никаких responses не зарегистрировано — любой реальный HTTP упал бы.
        key = MTPRotoKeyFactory(expired_date=self.future)

        get_update_key_service()(username=str(key.user.username))

        self.assertEqual(len(responses.calls), 0)

    def test_raises_when_no_active_key(self, mock_delay, mock_log) -> None:
        user = SystemUserFactory()

        with self.assertRaises(KeyDoesNotExist):
            get_update_key_service()(username=str(user.username))

    def test_raises_too_many_requests_within_cooldown(self, mock_delay, mock_log) -> None:
        key = MTPRotoKeyFactory(
            expired_date=self.future,
            last_update=timezone.now(),
        )

        with self.assertRaises(TooManyRequests):
            get_update_key_service()(username=str(key.user.username))
