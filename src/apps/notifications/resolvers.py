from __future__ import annotations

from typing import TYPE_CHECKING

from apps.notifications.enums import ContextResolverType

if TYPE_CHECKING:
    from apps.users.models import SystemUser


def resolve_context(*, resolver_type: ContextResolverType, user: SystemUser) -> dict[str, str] | None:
    """Возвращает персональный контекст для пользователя, или None если данных нет.

    Резолвер `None` (`continue` в рассылке) оставлен для будущих персональных
    контекстов. Ссылочный резолвер удалён вместе с reconcile-моделью: ключ
    валиден на всём флоте, ссылки на серверы бот строит на лету.
    """
    if resolver_type == ContextResolverType.NONE:
        return {}

    return {}
