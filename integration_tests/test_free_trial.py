"""Флоу 1: бесплатный ключ — FreeTrialClient.claim → POST /users/first-free-link/.

Полный путь: domain-клиент бота → живой Django → Celery push → все здоровые VDS.
"""

from __future__ import annotations

import datetime

from django.conf import settings

from . import config, db, helpers


def _expected_expired(days: int) -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    ).date().strftime("%d.%m.%y")


async def test_new_user_claim_issues_30day_key_without_link(username):
    clients = helpers.make_clients()
    assert await db.aw(db.count_healthy_vds)() >= 1, "нужен хотя бы один здоровый VDS"

    result = await clients.free_trial.claim(telegram_id=username)

    # ответ — только expired_date (= now+30д), без link
    assert result.expired_date == _expected_expired(settings.SUBSCRIPTION_PERIOD_DAYS)
    assert not hasattr(result, "link")

    # инвариант «одна строка на юзера»
    keys = await db.aw(db.get_keys)(username)
    assert len(keys) == 1
    token = keys[0].token

    # секрет доставлен (async push) на ВСЕ здоровые VDS, и это именно наш токен
    await helpers.assert_present_on_all_vds(username, present=True)
    secret = await helpers.vds_secret(config.VDS_VERIFY_URLS[0], username)
    assert secret is not None and token in secret


async def test_referred_user_before_limit_gets_30day_key(username):
    clients = helpers.make_clients()
    # реферал, лимит НЕ исчерпан → 30 дней (инвайт-бонус только после лимита)
    await db.aw(db.create_user)(username, invited_from_username="999inviter")

    result = await clients.free_trial.claim(telegram_id=username)

    assert result.expired_date == _expected_expired(30)
    user = await db.aw(db.get_user)(username)
    assert user.referral_activated is True
    await helpers.assert_present_on_all_vds(username, present=True)


async def test_referred_user_after_limit_gets_14day_key(username):
    clients = helpers.make_clients()
    await db.aw(db.create_user)(username, invited_from_username="999inviter")
    created = await db.aw(db.ensure_free_used_at_least)(
        settings.FIRST_MONTH_LIMIT, prefix="99953"
    )
    try:
        result = await clients.free_trial.claim(telegram_id=username)
        assert result.expired_date == _expected_expired(14)
        await helpers.assert_present_on_all_vds(username, present=True)
    finally:
        await db.aw(db.cleanup_users)(created)


async def test_exhausted_first_month_limit_gives_7day_key(username):
    clients = helpers.make_clients()
    # arrange: глобальный лимит бесплатных исчерпан
    created = await db.aw(db.ensure_free_used_at_least)(
        settings.FIRST_MONTH_LIMIT, prefix="99950"
    )
    try:
        result = await clients.free_trial.claim(telegram_id=username)
        assert result.expired_date == _expected_expired(7)
        await helpers.assert_present_on_all_vds(username, present=True)
    finally:
        await db.aw(db.cleanup_users)(created)
