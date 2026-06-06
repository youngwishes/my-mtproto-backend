from __future__ import annotations

from celery import shared_task


@shared_task
def send_mailing_task(mailing_id: int) -> None:
    from apps.notifications.selectors import get_mailing_by_id
    from apps.notifications.services.send_mailing_service import SendMailingService

    mailing = get_mailing_by_id(mailing_id=mailing_id)
    SendMailingService(mailing=mailing)()
