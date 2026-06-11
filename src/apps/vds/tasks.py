from __future__ import annotations

from celery import shared_task


@shared_task
def migrate_vds_keys_task(from_instance_id: int) -> None:
    from apps.vds.services import get_migrate_vds_keys_service

    get_migrate_vds_keys_service()(from_instance_id=from_instance_id)


@shared_task
def remove_user_keys_daily():
    from apps.vds.services import get_remove_expired_keys_daily_service

    get_remove_expired_keys_daily_service()()


@shared_task
def remove_expired_keys_from_vds_task(instance_id: int) -> None:
    from apps.vds.services.remove_expired_keys_from_vds_infra_service import get_remove_expired_keys_from_vds_infra_service

    get_remove_expired_keys_from_vds_infra_service()(instance_id=instance_id)


@shared_task
def add_key_to_another_vds_instances_task(exclude: int, username: str, secret: str) -> None:
    from apps.vds.services import get_add_key_to_another_vds_instances_service

    get_add_key_to_another_vds_instances_service()(exclude=exclude, username=username, secret=secret)


@shared_task
def update_key_on_another_vds_instances_task(exclude: int, username: str, secret: str) -> None:
    from apps.vds.services import get_update_key_on_another_vds_instances_service

    get_update_key_on_another_vds_instances_service()(exclude=exclude, username=username, secret=secret)


@shared_task
def remove_key_from_another_vds_instances_task(server: int, keys_id: list[int]) -> None:
    from apps.vds.services import get_remove_keys_from_vds_instance_infra_service

    get_remove_keys_from_vds_instance_infra_service()(server_id=server, keys_ids=keys_id)
