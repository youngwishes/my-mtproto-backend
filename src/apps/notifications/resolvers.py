from __future__ import annotations

from typing import TYPE_CHECKING

from apps.notifications.enums import ContextResolverType

if TYPE_CHECKING:
    from apps.users.models import SystemUser


def resolve_context(*, resolver_type: ContextResolverType, user: SystemUser) -> dict[str, str] | None:
    """Возвращает персональный контекст для пользователя, или None если данных нет."""
    if resolver_type == ContextResolverType.NONE:
        return {}

    resolvers = {
        ContextResolverType.ACTIVE_KEY_LINK: _resolve_active_key_link,
    }
    return resolvers[resolver_type](user)


def _resolve_active_key_link(user: SystemUser) -> dict[str, str] | None:
    """Возвращает ссылку на активный прокси-ключ пользователя."""
    from apps.vds.selectors import get_active_key

    key = get_active_key(user=user)
    if key is None:
        return None
    return {"link": key.get_proxy_link()}
