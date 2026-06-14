from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import QuerySet
from django.utils import timezone

from apps.vds.models import MTPRotoKey, VDSInstance

if TYPE_CHECKING:
    from datetime import date

    from apps.users.models import SystemUser


def get_active_key(*, user: SystemUser) -> MTPRotoKey | None:
    """Активный (не удалённый, не истёкший) ключ пользователя."""
    return MTPRotoKey.objects.filter(
        user=user,
        is_active=True,
        was_deleted=False,
        expired_date__gt=timezone.now(),
    ).first()


def get_least_populated_vds() -> VDSInstance | None:
    """Наименее загруженный VDS-сервер."""
    return VDSInstance.objects.get_least_populated()


def get_keys_by_username(*, username: str) -> QuerySet[MTPRotoKey]:
    """Все ключи пользователя по username."""
    return MTPRotoKey.objects.filter(user__username=username)


def get_keys_expiring_on_date(*, date: date) -> QuerySet[MTPRotoKey]:
    """Активные ключи, истекающие в указанную дату."""
    return MTPRotoKey.objects.active().filter(
        was_deleted=False,
        expired_date__date=date,
    )


def get_keys_expired_up_to_date(*, date: date) -> QuerySet[MTPRotoKey]:
    """Активные ключи, истекшие до указанной даты включительно."""
    return MTPRotoKey.objects.active().filter(
        was_deleted=False,
        expired_date__date__lte=date,
    )


def get_unnotified_keys_expiring_on_date(*, date: date) -> QuerySet[MTPRotoKey]:
    """Активные ключи, истекающие в указанную дату, о которых не уведомлён пользователь."""
    return get_keys_expiring_on_date(date=date).filter(user_notified=False)


def get_all_dead_expired_keys() -> QuerySet[MTPRotoKey]:
    """Все истёкшие ключи, помеченные как удалённые или неактивные."""
    from django.db.models import Q

    return MTPRotoKey.objects.filter(
        expired_date__date__lte=timezone.now().date(),
    ).filter(Q(was_deleted=True) | Q(is_active=False))


def get_all_active_vds_instances() -> QuerySet[VDSInstance]:
    """Все активные VDS-серверы."""
    return VDSInstance.objects.active()


def get_vds_instance_by_id(*, pk: int) -> VDSInstance:
    """VDS-сервер по первичному ключу."""
    return VDSInstance.objects.get(pk=pk)


def get_other_active_vds_instances(*, exclude_pk: int) -> QuerySet[VDSInstance]:
    """Все активные VDS-серверы, кроме указанного."""
    return VDSInstance.objects.active().exclude(pk=exclude_pk)


def get_keys_by_ids(*, ids: list[int]) -> QuerySet[MTPRotoKey]:
    """Ключи по списку первичных ключей."""
    return MTPRotoKey.objects.filter(pk__in=ids).select_related("user")


def get_key_by_id(*, pk: int) -> MTPRotoKey | None:
    """Один ключ по первичному ключу с подгруженным пользователем, или None."""
    return MTPRotoKey.objects.filter(pk=pk).select_related("user").first()


def get_all_active_valid_keys() -> QuerySet[MTPRotoKey]:
    """Все активные, не удалённые и не истёкшие ключи."""
    return MTPRotoKey.objects.filter(
        is_active=True,
        was_deleted=False,
        expired_date__gt=timezone.now(),
    ).select_related("user")


def get_unhealthy_vds_instances() -> QuerySet[VDSInstance]:
    """Активные VDS-серверы, помеченные как нездоровые."""
    return VDSInstance.objects.active().filter(is_healthy=False)


def get_healthy_vds_instances() -> QuerySet[VDSInstance]:
    """Активные здоровые VDS-серверы — цель доставки ключей."""
    return VDSInstance.objects.active().filter(is_healthy=True)


def count_active_valid_keys() -> int:
    """Количество активных валидных ключей — для глобального лимита."""
    return get_all_active_valid_keys().count()


def get_active_broadcast_keys(*, testing: bool = False) -> QuerySet[MTPRotoKey]:
    """Ключи для рассылки.

    testing=True — только тестовый пользователь (pk=562).
    testing=False — все оплатившие пользователи с активными ключами.
    """
    if testing:
        return MTPRotoKey.objects.filter(
            user__pk=562,
            is_active=True,
            was_deleted=False,
        ).select_related("user")
    return MTPRotoKey.objects.filter(
        is_active=True,
        was_deleted=False,
        user__first_month_free_used=True,
        expired_date__gt=timezone.now(),
    ).select_related("user")
