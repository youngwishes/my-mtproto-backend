from __future__ import annotations

from celery import shared_task

from apps.vpn.selectors import get_pending_vpn_ready_notifications
from apps.vpn.services.send_ready_notification import (
    get_send_vpn_ready_notification_service,
)


def _enqueue_notification(*, access_id: int, revision: int) -> None:
    send_vpn_ready_notification_task.delay(access_id=access_id, revision=revision)


@shared_task(
    bind=True,
    name="apps.vpn.send_ready_notification",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def send_vpn_ready_notification_task(self, *, access_id: int, revision: int) -> bool:
    return get_send_vpn_ready_notification_service()(
        access_id=access_id,
        revision=revision,
    )


@shared_task(name="apps.vpn.recover_ready_notifications")
def recover_vpn_ready_notifications_task() -> int:
    enqueued = 0
    for access in get_pending_vpn_ready_notifications():
        try:
            _enqueue_notification(
                access_id=access.pk,
                revision=access.published_revision,
            )
        except Exception:
            continue
        enqueued += 1
    return enqueued
