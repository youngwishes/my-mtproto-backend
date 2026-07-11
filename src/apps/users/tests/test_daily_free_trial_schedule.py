from __future__ import annotations

from django.conf import settings
from django.test import SimpleTestCase


class TestDailyFreeTrialSchedule(SimpleTestCase):
    def test_runs_every_day_at_noon_utc(self) -> None:
        entry = settings.CELERY_BEAT_SCHEDULE["grant-daily-free-trials"]

        self.assertEqual(entry["task"], "apps.users.tasks.grant_daily_free_trials_task")
        self.assertEqual(str(entry["schedule"]), "<crontab: 0 12 * * * (m/h/dM/MY/d)>")
