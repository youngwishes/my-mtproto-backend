import os

from celery.schedules import crontab

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
)

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
    "notify-vpn-expiry-day": {
        "task": "apps.vpn.tasks.notify_vpn_expiry_task",
        "schedule": crontab(hour=15, minute=0),
        "kwargs": {"window": "day"},
    },
    "notify-vpn-expiry-hour": {
        "task": "apps.vpn.tasks.notify_vpn_expiry_task",
        "schedule": crontab(hour=8, minute=0),
        "kwargs": {"window": "hour"},
    },
    "expire-vpn-subscriptions": {
        "task": "apps.vpn.tasks.expire_vpn_subscriptions_task",
        "schedule": crontab(hour=9, minute=0),
    },
    "notify-vpn-expiry-expired": {
        "task": "apps.vpn.tasks.notify_vpn_expiry_task",
        "schedule": crontab(hour=9, minute=5),
        "kwargs": {"window": "expired"},
    },
}
