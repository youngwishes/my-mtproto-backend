from __future__ import annotations

from django.db.models import QuerySet

from apps.notifications.enums import FilterType
from apps.notifications.models import Mailing, NotificationTemplate


def get_template(*, slug: str) -> NotificationTemplate:
    """Возвращает активный шаблон уведомления по slug."""
    return NotificationTemplate.objects.active().get(slug=slug)


def get_mailing_by_id(*, mailing_id: int) -> Mailing:
    """Возвращает рассылку по ID с подгруженным шаблоном."""
    return Mailing.objects.select_related("template").get(id=mailing_id)


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
