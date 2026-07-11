from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase

from apps.users.tasks import grant_daily_free_trials_task


class TestGrantDailyFreeTrialsTask(SimpleTestCase):
    @mock.patch("apps.users.services.get_daily_free_trial_grant_service")
    def test_delegates_to_service_from_factory(self, factory) -> None:
        service = factory.return_value

        grant_daily_free_trials_task()

        factory.assert_called_once_with()
        service.assert_called_once_with()
