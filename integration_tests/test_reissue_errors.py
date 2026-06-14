"""Флоу 5 (error-path): кулдаун, нет пользователя, нет активного ключа."""

from __future__ import annotations

import pytest

from src.exceptions import APIError

from . import db, helpers


async def test_reissue_cooldown_too_many_requests(username):
    clients = helpers.make_clients()
    await clients.free_trial.claim(telegram_id=username)
    await clients.links.reissue(telegram_id=username)  # выставляет last_update
    with pytest.raises(APIError) as ei:
        await clients.links.reissue(telegram_id=username)  # в пределах 5 минут
    helpers.assert_status(ei.value, "400")


async def test_reissue_no_user(username):
    clients = helpers.make_clients()
    with pytest.raises(APIError) as ei:
        await clients.links.reissue(telegram_id=username)
    helpers.assert_status(ei.value, "400")


async def test_reissue_no_active_key(username):
    clients = helpers.make_clients()
    await db.aw(db.create_expired_key)(username)
    with pytest.raises(APIError) as ei:
        await clients.links.reissue(telegram_id=username)
    helpers.assert_status(ei.value, "400")
