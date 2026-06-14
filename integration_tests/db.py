"""ORM-хелперы харнесса (вариант A): arrange/assert состояния бэкенда напрямую.

Все функции — синхронные (Django ORM). Из async-тестов звать через
``asgiref.sync.sync_to_async`` (см. ``aw`` ниже) или ``asyncio.to_thread``.
Импортировать только после ``django.setup()`` (делает conftest).
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from asgiref.sync import sync_to_async

from apps.users.models import SystemUser
from apps.vds.models import MTPRotoKey, VDSInstance

from . import config

_T = TypeVar("_T")


def aw(fn: Callable[..., _T]) -> Callable[..., Awaitable[_T]]:
    """Обернуть синхронную ORM-функцию в async (threadpool).

    После каждой операции закрываем соединение харнесса: вариант A делит один
    sqlite-файл с django/celery-контейнерами через bind-mount, и удержание
    открытого хэндла на хосте провоцирует у контейнера ``unable to open database
    file``. Закрытие освобождает файл между обращениями.
    """

    def _wrapped(*args: Any, **kwargs: Any) -> _T:
        from django.db import connection

        try:
            return fn(*args, **kwargs)
        finally:
            connection.close()

    return sync_to_async(_wrapped, thread_sensitive=True)


# --------------------------------------------------------------------------- #
# VDS-инстансы                                                                 #
# --------------------------------------------------------------------------- #
def ensure_local_vds(name: str = "it-local", location: str = "🧪 Local") -> VDSInstance:
    """Гарантировать здоровый VDSInstance, указывающий на локальный VDS-контейнер.

    ``internal_ip_address``/``port`` берутся из конфига так, чтобы celery-контейнер
    дотянулся до локального telemt-api (по умолчанию ``host.docker.internal:8080``).
    """
    vds, _ = VDSInstance.objects.update_or_create(
        name=name,
        defaults={
            "internal_ip_address": config.VDS_INTERNAL_IP,
            "port": config.VDS_PORT,
            "is_healthy": True,
            "is_active": True,
            "location": location,
        },
    )
    return vds


def count_healthy_vds() -> int:
    return VDSInstance.objects.active().filter(is_healthy=True).count()


def count_active_vds() -> int:
    return VDSInstance.objects.active().count()


def create_vds(name: str, **fields: Any) -> VDSInstance:
    vds, _ = VDSInstance.objects.update_or_create(name=name, defaults=fields)
    return vds


def delete_vds_by_name(name: str) -> None:
    VDSInstance.objects.filter(name=name).delete()


# --------------------------------------------------------------------------- #
# Пользователи / ключи                                                         #
# --------------------------------------------------------------------------- #
def get_user(username: str) -> SystemUser | None:
    return SystemUser.objects.filter(username=username).first()


def create_user(username: str, **fields: Any) -> SystemUser:
    """Создать/обновить тестового пользователя с произвольными полями (arrange)."""
    user, _ = SystemUser.objects.update_or_create(username=username, defaults=fields)
    return user


def free_used_count() -> int:
    """Глобальный счётчик исчерпавших бесплатный период (для FIRST_MONTH_LIMIT)."""
    return SystemUser.objects.filter(first_month_free_used=True).count()


def ensure_free_used_at_least(target: int, *, prefix: str) -> list[str]:
    """Догнать глобальный free_used_count до >= target синтетическими юзерами.

    Возвращает список созданных username (для очистки). Все — в безопасном
    префиксе (вне реального диапазона).
    """
    created: list[str] = []
    i = 0
    while free_used_count() < target:
        uname = f"{prefix}{i:05d}"
        SystemUser.objects.update_or_create(
            username=uname, defaults={"first_month_free_used": True}
        )
        created.append(uname)
        i += 1
    return created


def cleanup_users(usernames: list[str]) -> None:
    MTPRotoKey.objects.filter(user__username__in=usernames).delete()
    SystemUser.objects.filter(username__in=usernames).delete()


def create_referrals(inviter: str, *, total: int, active: int, prefix: str) -> list[str]:
    """Создать ``total`` рефералов пригласившего, из них ``active`` активированных.

    Возвращает список username рефералов (для очистки).
    """
    created: list[str] = []
    for i in range(total):
        uname = f"{prefix}{i:04d}"
        SystemUser.objects.update_or_create(
            username=uname,
            defaults={
                "invited_from_username": inviter,
                "referral_activated": i < active,
            },
        )
        created.append(uname)
    return created


def bulk_create_keys(owner_username: str, n: int, *, prefix: str = "itlim") -> str:
    """Создать ``n`` активных валидных ключей на одном юзере (для GLOBAL_KEYS_LIMIT)."""
    import os
    from datetime import timedelta

    from django.utils import timezone

    user, _ = SystemUser.objects.update_or_create(username=owner_username)
    exp = timezone.now() + timedelta(days=30)
    MTPRotoKey.objects.bulk_create(
        [
            MTPRotoKey(
                user=user,
                token=f"{prefix}{os.urandom(8).hex()}{i:06d}",
                expired_date=exp,
                is_active=True,
                was_deleted=False,
            )
            for i in range(n)
        ]
    )
    return owner_username


def create_expired_key(username: str) -> MTPRotoKey:
    """Создать пользователя с ИСТЁКШИМ ключом (нет активного ключа)."""
    import os
    from datetime import timedelta

    from django.utils import timezone

    user, _ = SystemUser.objects.update_or_create(username=username)
    return MTPRotoKey.objects.create(
        user=user,
        token=os.urandom(16).hex(),
        expired_date=timezone.now() - timedelta(days=1),
    )


def count_active_valid_keys() -> int:
    from apps.vds.selectors import count_active_valid_keys as _c

    return _c()


def count_payments(username: str) -> int:
    from apps.payments.models import Payment

    return Payment.objects.filter(user__username=username).count()


def key_secret_token(username: str) -> str | None:
    """get_secret_token() активного ключа (для сверки proxy_link в «Мои серверы»)."""
    key = get_active_key(username)
    return key.get_secret_token() if key else None


def get_keys(username: str) -> list[MTPRotoKey]:
    return list(MTPRotoKey.objects.filter(user__username=username))

def get_active_key(username: str) -> MTPRotoKey | None:
    return MTPRotoKey.objects.filter(
        user__username=username, is_active=True, was_deleted=False
    ).first()


# --------------------------------------------------------------------------- #
# Teardown                                                                     #
# --------------------------------------------------------------------------- #
def cleanup_user(username: str) -> None:
    """Удалить тестового пользователя и его ключи из БД (VDS чистится отдельно)."""
    MTPRotoKey.objects.filter(user__username=username).delete()
    SystemUser.objects.filter(username=username).delete()
