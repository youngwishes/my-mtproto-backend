from __future__ import annotations

from celery import shared_task


@shared_task
def send_mailing_task(mailing_id: int) -> None:
    from apps.notifications.selectors import get_mailing_by_id
    from apps.notifications.services.send_mailing_service import SendMailingService

    mailing = get_mailing_by_id(mailing_id=mailing_id)
    SendMailingService(mailing=mailing)()


@shared_task
def notify_before_removing_daily() -> None:
    from apps.notifications.services import get_notify_before_removing_daily_service

    get_notify_before_removing_daily_service()()


@shared_task
def notify_before_removing_daily_hour_before() -> None:
    from apps.notifications.services import get_notify_before_removing_hour_before_service

    get_notify_before_removing_hour_before_service()()


@shared_task
def broadcast_proxy_links_task(testing: bool = False) -> None:
    from apps.notifications.services import get_broadcast_proxy_links_service

    get_broadcast_proxy_links_service()(testing=testing)
