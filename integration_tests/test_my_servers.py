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


async def test_my_servers_no_active_key(username):
    clients = helpers.make_clients()
    await db.aw(db.create_expired_key)(username)
    with pytest.raises(APIError) as ei:
        await clients.links.get_my_servers(telegram_id=username)
    helpers.assert_status(ei.value, "400")
