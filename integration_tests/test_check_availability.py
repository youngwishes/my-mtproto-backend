"""Флоу 2: проверка доступности — FreeTrialClient.check_availability.

→ POST /users/check-first-free-link/ → FreeAvailable enum (без выдачи ключа).

ВНИМАНИЕ (зафиксировано владельцу): check и claim расходятся для реферала без
исчерпанного лимита — check отдаёт MONTH, а claim выдал бы 14 дней. Тесты ниже
отражают ФАКТИЧЕСКОЕ поведение check (TWO_WEEK только при лимите+инвайте).
Это не reconcile-баг (логика free-периода рефактором не трогалась).
"""

from __future__ import annotations

from django.conf import settings

from apps.users.enums import FreeAvailable

from . import db, helpers


async def test_new_user_month(username):
    clients = helpers.make_clients()
    period = await clients.free_trial.check_availability(
        telegram_id=username, telegram_username="tester"
    )
    assert period == FreeAvailable.MONTH.value


async def test_already_used_not_available(username):
    clients = helpers.make_clients()
    await db.aw(db.create_user)(username, first_month_free_used=True)
    period = await clients.free_trial.check_availability(
        telegram_id=username, telegram_username="tester"
    )
    assert period == FreeAvailable.NOT_AVAILABLE.value


async def test_limit_reached_without_invite_week(username):
    clients = helpers.make_clients()
    created = await db.aw(db.ensure_free_used_at_least)(
        settings.FIRST_MONTH_LIMIT, prefix="99951"
    )
    try:
        period = await clients.free_trial.check_availability(
            telegram_id=username, telegram_username="tester"
        )
        assert period == FreeAvailable.WEEK.value
    finally:
        await db.aw(db.cleanup_users)(created)


async def test_limit_reached_with_invite_two_week(username):
    clients = helpers.make_clients()
    created = await db.aw(db.ensure_free_used_at_least)(
        settings.FIRST_MONTH_LIMIT, prefix="99952"
    )
    try:
        period = await clients.free_trial.check_availability(
            telegram_id=username,
            telegram_username="tester",
            invited_from_username="999inviter",
        )
        assert period == FreeAvailable.TWO_WEEK.value
    finally:
        await db.aw(db.cleanup_users)(created)
