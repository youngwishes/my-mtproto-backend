from __future__ import annotations

from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

from apps.notifications.tasks import notify_mtproto_link_reissue_task


_SERVICE_FACTORY = "apps.notifications.services.get_notify_mtproto_link_reissue_service"
_TASK_NAME = "apps.notifications.tasks.notify_mtproto_link_reissue_task"


class TestNotifyMTPRotoLinkReissueTask(SimpleTestCase):
    @mock.patch(_SERVICE_FACTORY)
    def test_defaults_to_preview(self, service_factory: mock.Mock) -> None:
        service = service_factory.return_value

        notify_mtproto_link_reissue_task()

        service_factory.assert_called_once_with()
        service.assert_called_once_with(preview=True)

    @mock.patch(_SERVICE_FACTORY)
    def test_forwards_explicit_preview(self, service_factory: mock.Mock) -> None:
        service = service_factory.return_value

        notify_mtproto_link_reissue_task(preview=True)

        service_factory.assert_called_once_with()
        service.assert_called_once_with(preview=True)

    @mock.patch(_SERVICE_FACTORY)
    def test_forwards_explicit_mass_send(self, service_factory: mock.Mock) -> None:
        service = service_factory.return_value

        notify_mtproto_link_reissue_task(preview=False)

        service_factory.assert_called_once_with()
        service.assert_called_once_with(preview=False)

    def test_is_absent_from_beat_schedule(self) -> None:
        scheduled_tasks = {
            entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()
        }

        self.assertNotIn(_TASK_NAME, scheduled_tasks)
