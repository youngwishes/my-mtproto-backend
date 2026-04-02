from datetime import timedelta
from unittest import mock

import responses
from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.tasks import remove_user_keys_daily
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestRemoveUserTask(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory()
        self.key = MTPRotoKeyFactory(user=self.user, vds=self.server, expired_date=None)

    def _add_vds_response(self):
        responses.add(
            method=responses.POST,
            url=self.server.internal_url + "/api/v2/users/remove",
        )

    @mock.patch("apps.vds.services.remove_key_infra_service.RemoveUserKeyInfraService.__call__")
    def test_remove_user_task_case1(self, service) -> None:
        remove_user_keys_daily()
        self.assertEqual(service.call_count, 0)

    @mock.patch("apps.vds.services.remove_key_infra_service.RemoveUserKeyInfraService.__call__")
    def test_remove_user_task_case2(self, service) -> None:
        self.key.expired_date = timezone.now() + timedelta(days=1)
        self.key.save()
        remove_user_keys_daily()
        self.assertEqual(service.call_count, 0)

    @mock.patch("apps.core.bot.TelegramBot.send_message_deactivate_link")
    @responses.activate
    def test_remove_user_task_case3(self, deactivate) -> None:
        self._add_vds_response()
        self.key.expired_date = timezone.now()
        self.key.save()
        remove_user_keys_daily()
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(deactivate.call_count, 1)
        self.assertEqual(deactivate.call_args.kwargs["chat_id"], self.user.username)
        remove_user_keys_daily()
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(deactivate.call_count, 1)

    @mock.patch("apps.core.bot.TelegramBot.send_message_deactivate_link")
    @responses.activate
    def test_remove_user_task_case4(self, deactivate) -> None:
        self._add_vds_response()
        self.key.expired_date = timezone.now() - timedelta(days=1)
        self.key.save()
        remove_user_keys_daily()
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(deactivate.call_count, 1)
        self.assertEqual(deactivate.call_args.kwargs["chat_id"], self.user.username)
        remove_user_keys_daily()
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(deactivate.call_count, 1)
