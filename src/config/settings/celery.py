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
    "apps.vpn.health_check_nodes": {"queue": "celery"},
    "apps.vpn.reconcile_nodes": {"queue": "celery"},
    "apps.vpn.expire_accesses": {"queue": "celery"},
    "apps.vpn.send_ready_notification": {"queue": "celery"},
    "apps.vpn.recover_ready_notifications": {"queue": "celery"},
    "apps.vpn.collect_observability": {"queue": "celery"},
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
    "health-check-vpn-nodes": {
        "task": "apps.vpn.health_check_nodes",
        "schedule": timedelta(minutes=5),
    },
    "reconcile-vpn-nodes": {
        "task": "apps.vpn.reconcile_nodes",
        "schedule": timedelta(hours=1),
    },
    "expire-vpn-accesses": {
        "task": "apps.vpn.expire_accesses",
        "schedule": timedelta(minutes=1),
    },
    "recover-vpn-ready-notifications": {
        "task": "apps.vpn.recover_ready_notifications",
        "schedule": timedelta(minutes=1),
    },
    "collect-vpn-observability": {
        "task": "apps.vpn.collect_observability",
        "schedule": timedelta(minutes=1),
    },
}
