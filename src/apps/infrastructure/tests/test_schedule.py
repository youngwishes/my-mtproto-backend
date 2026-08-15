from __future__ import annotations

from django.conf import settings
from django.test import SimpleTestCase


class TestProjectServerPaymentReminderSchedule(SimpleTestCase):
    def test_runs_daily_at_eleven_utc(self) -> None:
        entry = settings.CELERY_BEAT_SCHEDULE["project-server-payment-reminder"]

        self.assertEqual(
            entry["task"],
            "apps.infrastructure.tasks.send_project_server_payment_reminder_task",
        )
        self.assertEqual(entry["schedule"]._orig_hour, 11)
        self.assertEqual(entry["schedule"]._orig_minute, 0)
        self.assertEqual(settings.TIME_ZONE, "UTC")
