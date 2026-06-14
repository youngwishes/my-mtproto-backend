"""Флоу 5: перевыпуск — LinksClient.reissue → POST /users/update-link/.

Happy-path: новый token, тот же expired_date, ответ без link, ротация секрета
на ВСЕХ VDS (новый токен доставлен, старый заменён).
"""

from __future__ import annotations

from . import config, db, helpers


async def test_reissue_rotates_token_same_expiry_and_delivers_to_all_vds(username):
    clients = helpers.make_clients()
    # arrange: активный ключ + секрет на VDS
    await clients.free_trial.claim(telegram_id=username)
    await helpers.assert_present_on_all_vds(username, present=True)
    key1 = await db.aw(db.get_active_key)(username)
    token1, expiry1 = key1.token, key1.expired_date
    secret_before = await helpers.vds_secret(config.VDS_VERIFY_URLS[0], username)
    assert token1 in secret_before

    # act
    result = await clients.links.reissue(telegram_id=username)

    # новый токен в БД, тот же срок, ответ без link
    key2 = await db.aw(db.get_active_key)(username)
    assert key2.token != token1
    assert key2.expired_date == expiry1
    assert result.expired_date == expiry1.date().strftime("%d.%m.%y")
    assert not hasattr(result, "link")

    # инвариант «одна строка»
    assert len(await db.aw(db.get_keys)(username)) == 1

    # ротация доехала до ВСЕХ VDS: новый токен присутствует, старого больше нет
    new_token = key2.token

    async def rotated() -> bool:
        s = await helpers.vds_secret(config.VDS_VERIFY_URLS[0], username)
        return s is not None and new_token in s and token1 not in s

    assert await helpers.wait_until(rotated), (
        "перевыпущенный секрет не доставлен на VDS — ротация не доехала"
    )
