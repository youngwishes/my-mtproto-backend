import os

from celery.schedules import crontab

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
)

CELERY_BEAT_SCHEDULE = {
    "run-my-task-every-minute": {
        "task": "apps.vds.tasks.remove_user_keys_daily",
        'schedule': crontab(hour=6, minute=0),
    },
}
