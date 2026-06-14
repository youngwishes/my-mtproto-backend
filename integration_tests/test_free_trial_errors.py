"""Флоу 1 (error-path): повторная выдача и глобальный лимит ключей."""

from __future__ import annotations

import pytest
from django.conf import settings

from src.exceptions import APIError

from . import config, db, helpers


async def test_claim_twice_raises_already_used(username):
    clients = helpers.make_clients()
    await clients.free_trial.claim(telegram_id=username)
    with pytest.raises(APIError) as ei:
        await clients.free_trial.claim(telegram_id=username)
    helpers.assert_status(ei.value, "400")
    # новый ключ не создан — по-прежнему ровно один
    assert len(await db.aw(db.get_keys)(username)) == 1


async def test_global_keys_limit_reached(username):
    clients = helpers.make_clients()
    owner = "999keylimit"
    await db.aw(db.cleanup_user)(owner)
    await db.aw(db.bulk_create_keys)(owner, settings.GLOBAL_KEYS_LIMIT)
    try:
        assert await db.aw(db.count_active_valid_keys)() >= settings.GLOBAL_KEYS_LIMIT
        with pytest.raises(APIError) as ei:
            await clients.free_trial.claim(telegram_id=username)
        helpers.assert_status(ei.value, "400")
        # ключ не выдан и на VDS ничего не запушено
        assert len(await db.aw(db.get_keys)(username)) == 0
        assert await helpers.vds_has(config.VDS_VERIFY_URLS[0], username) is False
    finally:
        await db.aw(db.cleanup_user)(owner)
