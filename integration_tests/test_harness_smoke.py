"""Smoke-проверка каркаса: pytest+asyncio, Django ORM, клиенты бота, доступность VDS.

Не требует запущенного backend-стека — только локальный VDS (:8080).
Если этот файл зелёный, инфраструктура харнесса исправна.
"""

from __future__ import annotations

from . import config, db, helpers


def test_django_orm_reachable() -> None:
    # ORM делит живую БД с контейнерами; запрос не должен падать.
    assert db.count_healthy_vds() >= 0


def test_bot_clients_instantiate() -> None:
    clients = helpers.make_clients()
    assert clients.free_trial.backend.base_url == config.BACKEND_URL


async def test_vds_reachable_and_user_absent() -> None:
    # VDS поднят; случайный синтетический пользователь отсутствует → 404 → False.
    username = helpers.make_test_id()
    for verify_url in config.VDS_VERIFY_URLS:
        assert await helpers.vds_has(verify_url, username) is False
