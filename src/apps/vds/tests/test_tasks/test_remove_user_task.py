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
        self.user = SystemUserFactory(username="123456789")
        self.key = MTPRotoKeyFactory(user=self.user, vds=self.server, expired_date=None)

    def _add_vds_response(self):
        responses.add(
            method=responses.DELETE,
            url=self.server.internal_url + "/api/users",
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

    @mock.patch("apps.vds.tasks.time.sleep")
    @mock.patch("apps.vds.tasks.get_template")
    @mock.patch("apps.vds.tasks.send")
    @responses.activate
    def test_remove_user_task_case3(self, mock_send, mock_get_template, _sleep) -> None:
        mock_rendered = mock.Mock()
        mock_rendered.text = "Your link has been deactivated"
        mock_rendered.markup = None
        mock_get_template.return_value.render.return_value = mock_rendered

        self._add_vds_response()
        self.key.expired_date = timezone.now()
        self.key.save()
        remove_user_keys_daily()
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args.kwargs["chat_id"], int(self.user.username))
        remove_user_keys_daily()
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(mock_send.call_count, 1)

    @mock.patch("apps.vds.tasks.time.sleep")
    @mock.patch("apps.vds.tasks.get_template")
    @mock.patch("apps.vds.tasks.send")
    @responses.activate
    def test_remove_user_task_case4(self, mock_send, mock_get_template, _sleep) -> None:
        mock_rendered = mock.Mock()
        mock_rendered.text = "Your link has been deactivated"
        mock_rendered.markup = None
        mock_get_template.return_value.render.return_value = mock_rendered

        self._add_vds_response()
        self.key.expired_date = timezone.now() - timedelta(days=1)
        self.key.save()
        remove_user_keys_daily()
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args.kwargs["chat_id"], int(self.user.username))
        remove_user_keys_daily()
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(mock_send.call_count, 1)
