from __future__ import annotations

from unittest import mock

import responses
from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.tasks import remove_user_keys_daily
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestRemoveUserKeysTask(TestCase):
    @responses.activate
    @mock.patch("apps.vds.services.remove_expired_keys_daily_service.time")
    @mock.patch("apps.vds.services.remove_expired_keys_daily_service.get_template")
    @mock.patch("apps.vds.services.remove_expired_keys_daily_service.send_telegram_message")
    def test_delegates_to_service(self, _send, mock_get_template, _time) -> None:
        server = VDSInstanceFactory()
        user = SystemUserFactory(username="123456789")
        MTPRotoKeyFactory(user=user, expired_date=timezone.now())
        responses.add(method=responses.DELETE, url=server.internal_url + "/api/users")
        mock_get_template.return_value.render.return_value = mock.Mock(text="deactivated", markup=None)

        remove_user_keys_daily()

        self.assertEqual(len(responses.calls), 1)
