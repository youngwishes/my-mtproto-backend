"""Флоу 6: мои серверы — LinksClient.get_my_servers → POST /users/my-servers/."""

from __future__ import annotations

import pytest

from src.exceptions import APIError

from . import db, helpers


async def test_my_servers_lists_active_vds_with_proxy_links(username):
    clients = helpers.make_clients()
    await clients.free_trial.claim(telegram_id=username)
    expected_secret = await db.aw(db.key_secret_token)(username)

    result = await clients.links.get_my_servers(telegram_id=username)

    active_count = await db.aw(db.count_active_vds)()
    assert len(result.servers) == active_count >= 1
    for server in result.servers:
        # хост — субдомен сервера {name}.beatvault.ru, секрет из get_secret_token (TLS_DOMAIN)
        assert ".beatvault.ru" in server.proxy_link
        assert expected_secret in server.proxy_link
        assert server.location


async def test_my_servers_excludes_inactive_vds(username):
    clients = helpers.make_clients()
    await clients.free_trial.claim(telegram_id=username)
    await db.aw(db.create_vds)(
        "it-inactive",
        number=99099,
        ip_address="203.0.113.99",
        internal_ip_address="127.0.0.1",
        port=9,
        is_active=False,
    )
    try:
        result = await clients.links.get_my_servers(telegram_id=username)
        assert all("it-inactive" not in s.proxy_link for s in result.servers)
    finally:
        await db.aw(db.delete_vds_by_name)("it-inactive")


async def test_my_servers_no_active_key_when_free_already_used(username):
    # Период уже израсходован, ключ истёк → повторной авто-активации нет, 400.
    clients = helpers.make_clients()
    await db.aw(db.create_user)(username, first_month_free_used=True)
    await db.aw(db.create_expired_key)(username)
    with pytest.raises(APIError) as ei:
        await clients.links.get_my_servers(telegram_id=username)
    helpers.assert_status(ei.value, "400")


async def test_my_servers_auto_activates_free_period_for_new_user(username):
    # Новый пользователь (без ключа, период не использован) жмёт «Мои серверы» →
    # бесплатный период активируется на 30 дней, и сразу возвращается список
    # серверов; секрет реально доставляется на все здоровые VDS (async push).
    clients = helpers.make_clients()
    assert await db.aw(db.count_healthy_vds)() >= 1, "нужен хотя бы один здоровый VDS"
    assert await db.aw(db.get_active_key)(username) is None

    result = await clients.links.get_my_servers(telegram_id=username)

    # период активирован, выдан ровно один 30-дневный ключ
    user = await db.aw(db.get_user)(username)
    assert user is not None and user.first_month_free_used is True
    keys = await db.aw(db.get_keys)(username)
    assert len(keys) == 1
    assert result.expired_date == helpers.expected_expired(30)

    # серверы возвращены и секрет доставлен на ВСЕ VDS — это именно наш токен
    active_count = await db.aw(db.count_active_vds)()
    assert len(result.servers) == active_count >= 1
    await helpers.assert_present_on_all_vds(username, present=True)
    expected_secret = await db.aw(db.key_secret_token)(username)
    for server in result.servers:
        assert ".beatvault.ru" in server.proxy_link
        assert expected_secret in server.proxy_link
