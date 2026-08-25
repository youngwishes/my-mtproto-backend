from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import QuerySet
from django.utils import timezone

from apps.notifications.enums import FilterType
from apps.notifications.models import Mailing, NotificationTemplate
from apps.users.models import SystemUser
from apps.vds.models import MTPRotoKey

if TYPE_CHECKING:
    from datetime import datetime


def get_template(*, slug: str) -> NotificationTemplate:
    """Возвращает активный шаблон уведомления по slug."""
    return NotificationTemplate.objects.active().get(slug=slug)


def get_mailing_by_id(*, mailing_id: int) -> Mailing:
    """Возвращает рассылку по ID с подгруженным шаблоном."""
    return Mailing.objects.select_related("template").get(id=mailing_id)


def mark_key_notified_for_expiry(*, key_id: int, expired_date: datetime) -> bool:
    """Отмечает уведомление, только пока выбранный срок ключа не изменился."""
    return (
        MTPRotoKey.objects.filter(
            pk=key_id,
            expired_date=expired_date,
            user_notified=False,
        ).update(user_notified=True)
        == 1
    )


def get_mtproto_link_reissue_recipients() -> QuerySet[SystemUser]:
    eligible_user_ids = MTPRotoKey.objects.active().filter(
        was_deleted=False,
        expired_date__gt=timezone.now(),
    ).values("user_id")
    return SystemUser.objects.filter(pk__in=eligible_user_ids).distinct()


def get_users_by_filter(*, filter_type: int, params: dict) -> QuerySet:
    """Возвращает QuerySet пользователей по типу фильтра рассылки."""
    filters = {
        FilterType.ALL_ACTIVE: _all_active_users,
        FilterType.EXPIRING_SOON: _expiring_soon,
        FilterType.NOT_SUBSCRIBED: _not_subscribed,
    }
    return filters[filter_type](params)


def _all_active_users(params: dict) -> QuerySet:
    from apps.users.models import SystemUser

    return SystemUser.objects.filter(is_active=True)


def _expiring_soon(params: dict) -> QuerySet:
    from datetime import timedelta

    from django.utils.timezone import now

    from apps.users.models import SystemUser

    days = params.get("days_until_expiry", 1)
    deadline = now() + timedelta(days=days)
    return SystemUser.objects.filter(
        keys__expired_date__lte=deadline,
        keys__was_deleted=False,
    ).distinct()


def _not_subscribed(params: dict) -> QuerySet:
    """TODO: возвращает всех активных — фильтрация по подписке на канал не реализована.

    После добавления поля is_channel_member в SystemUser и celery-задачи для его
    периодического обновления — заменить на фильтр по этому полю.
    """
    from apps.users.models import SystemUser

    return SystemUser.objects.filter(is_active=True)
