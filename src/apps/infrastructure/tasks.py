from __future__ import annotations

from typing import TYPE_CHECKING

from celery import shared_task
from django.utils import timezone

from apps.infrastructure.services import get_project_server_payment_reminder_service

if TYPE_CHECKING:
    from celery.app.task import Task


@shared_task(bind=True, max_retries=3)
def send_project_server_payment_reminder_task(self: Task) -> None:
    try:
        get_project_server_payment_reminder_service()(today=timezone.localdate())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
