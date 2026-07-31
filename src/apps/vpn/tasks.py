from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import requests
from celery import shared_task
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.html import escape

from apps.core.telegram.transport import send_telegram_message
from apps.vpn.exceptions import UnsupportedVPNProfileOperation
from apps.vpn.selectors import get_vpn_instance_by_id, get_vpn_subscription_by_id
from apps.vpn.services.dtos import NodeProfileDTO
from apps.vpn.services.node_client_service import get_node_client_service

if TYPE_CHECKING:
    from apps.vpn.models import VPNInstance, VPNSubscription


ProfileOperation = Literal["put", "delete"]


def _notify_delivery_failure(
    *,
    subscription: VPNSubscription,
    instance: VPNInstance,
    operation: ProfileOperation,
) -> None:
    """Сообщает админу о terminal delivery без credentials пользователя."""
    send_telegram_message(
        chat_id=settings.MY_TELEGRAM_ID,
        text=(
            "🔴 <b>(BACKEND) VPN delivery failed</b>\n\n"
            f"- Пользователь: <b>{escape(subscription.user.username)}</b>\n"
            f"- VPN-нода: <b>{escape(instance.name)}</b>\n"
            f"- Операция: <b>{operation.upper()}</b>"
        ),
        timeout=settings.TELEGRAM_TIMEOUT,
    )


@shared_task(bind=True, max_retries=3)
def deliver_vpn_profile_task(
    self,
    subscription_id: int,
    instance_id: int,
    operation: ProfileOperation,
) -> None:
    """Доставляет idempotent PUT/DELETE одной subscription на одну VPN-ноду."""
    subscription = get_vpn_subscription_by_id(subscription_id=subscription_id)
    instance = get_vpn_instance_by_id(instance_id=instance_id)
    if subscription is None or instance is None:
        return

    try:
        client = get_node_client_service()
        if operation == "put":
            client.put_profile(
                instance=instance,
                profile=NodeProfileDTO(
                    access_id=subscription.pk,
                    vless_uuid=str(subscription.vless_uuid),
                    hysteria_secret=subscription.hysteria_secret,
                ),
            )
        elif operation == "delete":
            client.delete_profile(instance=instance, access_id=subscription.pk)
        else:
            raise UnsupportedVPNProfileOperation(operation)
    except ImproperlyConfigured:
        _notify_delivery_failure(
            subscription=subscription,
            instance=instance,
            operation=operation,
        )
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code is not None and 400 <= status_code < 500:
            _notify_delivery_failure(
                subscription=subscription,
                instance=instance,
                operation=operation,
            )
            return
        _retry_or_notify(
            task=deliver_vpn_profile_task,
            exc=exc,
            subscription=subscription,
            instance=instance,
            operation=operation,
        )
    except (requests.Timeout, requests.ConnectionError) as exc:
        _retry_or_notify(
            task=deliver_vpn_profile_task,
            exc=exc,
            subscription=subscription,
            instance=instance,
            operation=operation,
        )


def _retry_or_notify(
    *,
    task,
    exc: Exception,
    subscription: VPNSubscription,
    instance: VPNInstance,
    operation: ProfileOperation,
) -> None:
    if task.request.retries >= task.max_retries:
        _notify_delivery_failure(
            subscription=subscription,
            instance=instance,
            operation=operation,
        )
        return
    raise task.retry(exc=exc, countdown=10)
