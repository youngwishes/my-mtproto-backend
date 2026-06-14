from __future__ import annotations

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError


def _handle_replication_failure(*, server_id: int, username: str, exc: Exception) -> None:
    """Вызывается когда все ретраи репликации на сервер исчерпаны."""
    from apps.core.telegram.transport import send_telegram_message
    from django.conf import settings
    from django.utils import html

    from apps.vds.models import VDSInstance

    VDSInstance.objects.filter(pk=server_id).update(is_healthy=False)

    try:
        server = VDSInstance.objects.get(pk=server_id)
        server_info = f"#{server.number} ({server.internal_url})"
    except VDSInstance.DoesNotExist:
        server_info = f"ID={server_id}"

    escaped_error = html.escape(str(exc))
    send_telegram_message(
        chat_id=int(settings.MY_TELEGRAM_ID),
        text=(
            "🔴 <b>(BACKEND) Системное оповещение</b>\n\n"
            "🛡 <b>Тип ошибки:</b> REPLICATION FAILED (все ретраи исчерпаны)\n"
            "📋 <b>Детали:</b>\n"
            f"- Сервер — <b>{server_info}</b>\n"
            f"- Пользователь — <b>{username}</b>\n\n"
            f"<code>{escaped_error}</code>\n\n"
            "⚙️ <i>Сервер помечен как нездоровый. Health-check восстановит его автоматически.</i>"
        ),
    )


@shared_task
def migrate_vds_keys_task(from_instance_id: int) -> None:
    from apps.vds.services import get_migrate_vds_keys_service

    get_migrate_vds_keys_service()(from_instance_id=from_instance_id)


@shared_task
def remove_user_keys_daily():
    from apps.vds.services import get_remove_expired_keys_daily_service

    get_remove_expired_keys_daily_service()()


@shared_task
def remove_dead_keys_from_vds_task(instance_id: int) -> None:
    from apps.vds.services.remove_dead_keys_from_vds_infra_service import get_remove_dead_keys_from_vds_infra_service

    get_remove_dead_keys_from_vds_infra_service()(instance_id=instance_id)


@shared_task
def add_key_to_another_vds_instances_task(exclude: int, username: str, secret: str) -> None:
    from apps.vds.selectors import get_other_active_vds_instances

    for server in get_other_active_vds_instances(exclude_pk=exclude):
        replicate_key_add_to_server_task.delay(server.pk, username, secret)


@shared_task(bind=True, max_retries=3)
def replicate_key_add_to_server_task(self, server_id: int, username: str, secret: str) -> None:
    from apps.vds.services.replicate_key_add_to_server_infra_service import (
        get_replicate_key_add_to_server_infra_service,
    )

    try:
        get_replicate_key_add_to_server_infra_service()(
            server_id=server_id, username=username, secret=secret
        )
    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=60 * (4 ** self.request.retries))
        except MaxRetriesExceededError:
            _handle_replication_failure(server_id=server_id, username=username, exc=exc)


@shared_task
def update_key_on_another_vds_instances_task(exclude: int, username: str, secret: str) -> None:
    from apps.vds.selectors import get_other_active_vds_instances

    for server in get_other_active_vds_instances(exclude_pk=exclude):
        replicate_key_update_to_server_task.delay(server.pk, username, secret)


@shared_task(bind=True, max_retries=3)
def replicate_key_update_to_server_task(self, server_id: int, username: str, secret: str) -> None:
    from apps.vds.services.replicate_key_update_to_server_infra_service import (
        get_replicate_key_update_to_server_infra_service,
    )

    try:
        get_replicate_key_update_to_server_infra_service()(
            server_id=server_id, username=username, secret=secret
        )
    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=60 * (4 ** self.request.retries))
        except MaxRetriesExceededError:
            _handle_replication_failure(server_id=server_id, username=username, exc=exc)


@shared_task
def push_key_to_servers_task(key_id: int) -> None:
    """Мгновенный пинок: доставить один ключ на все здоровые VDS."""
    from apps.vds.selectors import get_healthy_vds_instances, get_key_by_id

    key = get_key_by_id(pk=key_id)
    if key is None or not getattr(key.user, "username", None) or not key.token:
        return

    for server in get_healthy_vds_instances():
        push_key_to_server_task.delay(server.pk, key.user.username, key.token)


@shared_task(bind=True, max_retries=3)
def push_key_to_server_task(self, server_id: int, username: str, secret: str) -> None:
    from apps.vds.services.push_key_to_server_infra_service import (
        get_push_key_to_server_infra_service,
    )

    try:
        get_push_key_to_server_infra_service()(
            server_id=server_id, username=username, secret=secret
        )
    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=60 * (4 ** self.request.retries))
        except MaxRetriesExceededError:
            _handle_replication_failure(server_id=server_id, username=username, exc=exc)


@shared_task
def remove_key_from_another_vds_instances_task(server: int, keys_id: list[int]) -> None:
    from apps.vds.services import get_remove_keys_from_vds_instance_infra_service

    get_remove_keys_from_vds_instance_infra_service()(server_id=server, keys_ids=keys_id)


@shared_task
def sync_keys_to_vds_task(instance_id: int) -> None:
    from apps.vds.services import get_sync_keys_to_vds_infra_service

    get_sync_keys_to_vds_infra_service()(instance_id=instance_id)


@shared_task
def check_vds_health_task() -> None:
    from apps.vds.selectors import get_unhealthy_vds_instances
    from apps.vds.services.vds_health_check_infra_service import get_vds_health_check_infra_service

    service = get_vds_health_check_infra_service()
    for server in get_unhealthy_vds_instances():
        if service(instance_id=server.pk):
            server.is_healthy = True
            server.save(update_fields=["is_healthy"])
            sync_keys_to_vds_task.delay(instance_id=server.pk)
