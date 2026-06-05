from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone

from apps.vds.models import MTPRotoKey

if TYPE_CHECKING:
    from apps.users.models import SystemUser


def get_active_key(*, user: SystemUser) -> MTPRotoKey | None:
    """Активный (не удалённый, не истёкший) ключ пользователя."""
    return MTPRotoKey.objects.filter(
        user=user,
        was_deleted=False,
        expired_date__gt=timezone.now(),
    ).first()
