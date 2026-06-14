from __future__ import annotations

from datetime import timedelta
from unittest import mock

import responses
from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.services import get_remove_expired_keys_daily_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestRemoveExpiredKeysDailyService(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory(username="123456789")
        self.key = MTPRotoKeyFactory(user=self.user, expired_date=None)

    def _add_vds_response(self):
        responses.add(
            method=responses.DELETE,
            url=self.server.internal_url + "/api/users",
        )

    @mock.patch("apps.vds.services.remove_key_infra_service.RemoveUserKeyInfraService.__call__")
    def test_no_expired_keys_exits_early(self, infra_service) -> None:
        get_remove_expired_keys_daily_service()()
        self.assertEqual(infra_service.call_count, 0)

    @mock.patch("apps.vds.services.remove_key_infra_service.RemoveUserKeyInfraService.__call__")
    def test_future_key_is_not_removed(self, infra_service) -> None:
        self.key.expired_date = timezone.now() + timedelta(days=1)
        self.key.save()
        get_remove_expired_keys_daily_service()()
        self.assertEqual(infra_service.call_count, 0)

    @responses.activate
    @mock.patch("apps.vds.services.remove_expired_keys_daily_service.time")
    @mock.patch("apps.vds.services.remove_expired_keys_daily_service.get_template")
    @mock.patch("apps.vds.services.remove_expired_keys_daily_service.send_telegram_message")
    def test_expired_today_removes_key_and_notifies(self, mock_send, mock_get_template, _time) -> None:
        mock_get_template.return_value.render.return_value = mock.Mock(text="deactivated", markup=None)
        self._add_vds_response()
        self.key.expired_date = timezone.now()
        self.key.save()

        get_remove_expired_keys_daily_service()()

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args.kwargs["chat_id"], int(self.user.username))

        self.key.refresh_from_db()
        self.assertFalse(self.key.is_active)
        self.assertTrue(self.key.was_deleted)

        # второй вызов — ключ уже деактивирован, ничего не делает
        get_remove_expired_keys_daily_service()()
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(mock_send.call_count, 1)

    @responses.activate
    @mock.patch("apps.vds.services.remove_expired_keys_daily_service.time")
    @mock.patch("apps.vds.services.remove_expired_keys_daily_service.get_template")
    @mock.patch("apps.vds.services.remove_expired_keys_daily_service.send_telegram_message")
    def test_expired_yesterday_removes_key_and_notifies(self, mock_send, mock_get_template, _time) -> None:
        mock_get_template.return_value.render.return_value = mock.Mock(text="deactivated", markup=None)
        self._add_vds_response()
        self.key.expired_date = timezone.now() - timedelta(days=1)
        self.key.save()

        get_remove_expired_keys_daily_service()()

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args.kwargs["chat_id"], int(self.user.username))

        self.key.refresh_from_db()
        self.assertFalse(self.key.is_active)
        self.assertTrue(self.key.was_deleted)

        # второй вызов — ключ уже деактивирован, ничего не делает
        get_remove_expired_keys_daily_service()()
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(mock_send.call_count, 1)
