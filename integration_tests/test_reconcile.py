"""Флоу 8: reconcile / отказоустойчивость доставки и дневное удаление."""

from __future__ import annotations

from . import config, db, helpers


async def test_unhealthy_vds_skipped_on_issue(username):
    clients = helpers.make_clients()
    # нездоровый недостижимый VDS не должен мешать выдаче и пушу на здоровые
    await db.aw(db.create_vds)(
        "it-unhealthy",
        number=99098,
        ip_address="203.0.113.98",
        internal_ip_address="203.0.113.250",  # TEST-NET, недостижим
        port=9,
        is_active=True,
        is_healthy=False,
    )
    try:
        await clients.free_trial.claim(telegram_id=username)
        # секрет доехал на здоровый VDS; нездоровый пропущен (фан-аут только по healthy)
        await helpers.assert_present_on_all_vds(username, present=True)
    finally:
        await db.aw(db.delete_vds_by_name)("it-unhealthy")


async def test_daily_removal_deletes_expired_key_from_vds(username):
    # arrange: истёкший ключ, секрет присутствует на VDS
    key = await db.aw(db.create_expired_key)(username)
    await helpers.vds_post(config.VDS_VERIFY_URLS[0], username, key.token)
    assert await helpers.vds_has(config.VDS_VERIFY_URLS[0], username) is True

    # триггер дневного удаления (в django-контейнере)
    await helpers.run_daily_removal()

    # ключ удалён со всех VDS и помечен в БД
    await helpers.assert_present_on_all_vds(username, present=False)
    refreshed = await db.aw(db.get_key_by_pk)(key.pk)
    assert refreshed.was_deleted is True
    assert refreshed.is_active is False
