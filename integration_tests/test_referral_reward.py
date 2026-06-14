"""Флоу 4: реферальная награда — ReferralsClient.claim_reward → POST /users/referral/link/."""

from __future__ import annotations

import pytest
from django.conf import settings

from src.exceptions import APIError

from . import db, helpers


async def test_reward_with_enough_referrals_gives_14day_key(username):
    clients = helpers.make_clients()
    await db.aw(db.create_user)(username)
    refs = await db.aw(db.create_referrals)(
        username, total=settings.INVITE_MUST_COUNT, active=settings.INVITE_MUST_COUNT,
        prefix=f"{username}r",
    )
    try:
        result = await clients.referrals.claim_reward(telegram_id=username)
        assert result.expired_date == helpers.expected_expired(14)
        assert not hasattr(result, "link")
        await helpers.assert_present_on_all_vds(username, present=True)
        user = await db.aw(db.get_user)(username)
        assert user.referral_link_activated_count == 1
    finally:
        await db.aw(db.cleanup_users)(refs)


async def test_reward_extends_active_key_by_14_days(username):
    clients = helpers.make_clients()
    key = await db.aw(db.create_active_key)(username, days=20)
    token1, exp1 = key.token, key.expired_date
    refs = await db.aw(db.create_referrals)(
        username, total=settings.INVITE_MUST_COUNT, active=settings.INVITE_MUST_COUNT,
        prefix=f"{username}r",
    )
    try:
        await clients.referrals.claim_reward(telegram_id=username)
        key2 = await db.aw(db.get_active_key)(username)
        assert key2.token == token1                       # ключ не пересоздан
        assert (key2.expired_date - exp1).days == 14      # +14 к прежнему сроку
        assert len(await db.aw(db.get_keys)(username)) == 1
    finally:
        await db.aw(db.cleanup_users)(refs)


async def test_reward_not_enough_referrals(username):
    clients = helpers.make_clients()
    await db.aw(db.create_user)(username)
    refs = await db.aw(db.create_referrals)(
        username, total=settings.INVITE_MUST_COUNT - 1,
        active=settings.INVITE_MUST_COUNT - 1, prefix=f"{username}r",
    )
    try:
        with pytest.raises(APIError) as ei:
            await clients.referrals.claim_reward(telegram_id=username)
        helpers.assert_status(ei.value, "400")
    finally:
        await db.aw(db.cleanup_users)(refs)


async def test_reward_already_claimed(username):
    clients = helpers.make_clients()
    # награду уже забирали (лимит REFERRAL_LINKS_LIMIT исчерпан)
    await db.aw(db.create_user)(
        username, referral_link_activated_count=settings.REFERRAL_LINKS_LIMIT
    )
    refs = await db.aw(db.create_referrals)(
        username, total=settings.INVITE_MUST_COUNT, active=settings.INVITE_MUST_COUNT,
        prefix=f"{username}r",
    )
    try:
        with pytest.raises(APIError) as ei:
            await clients.referrals.claim_reward(telegram_id=username)
        helpers.assert_status(ei.value, "400")
    finally:
        await db.aw(db.cleanup_users)(refs)
