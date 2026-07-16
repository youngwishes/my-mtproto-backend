from __future__ import annotations

import os
from datetime import timedelta

from celery.schedules import crontab

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
)
CELERY_TASK_ROUTES = {
    "apps.vpn.apply_payment_receipt": {"queue": "vpn_payment_fulfillment"},
    "apps.vpn.recover_payment_receipts": {"queue": "celery"},
}

CELERY_BEAT_SCHEDULE = {
    "remove_user_keys_daily": {
        "task": "apps.vds.tasks.remove_user_keys_daily",
        "schedule": crontab(hour=9, minute=0),
    },
    "notify_before_removing_daily": {
        "task": "apps.notifications.tasks.notify_before_removing_daily",
        "schedule": crontab(hour=15, minute=0),
    },
    "notify_before_removing_daily_hour_before": {
        "task": "apps.notifications.tasks.notify_before_removing_daily_hour_before",
        "schedule": crontab(hour=8, minute=0),
    },
    "check-vds-health": {
        "task": "apps.vds.tasks.check_vds_health_task",
        "schedule": crontab(minute="*/5"),
    },
    "grant-daily-free-trials": {
        "task": "apps.users.tasks.grant_daily_free_trials_task",
        "schedule": crontab(hour=12, minute=0),
    },
    "recover-vpn-payment-receipts": {
        "task": "apps.vpn.recover_payment_receipts",
        "schedule": timedelta(minutes=1),
    },
}
