from __future__ import annotations

import httpx
import pytest
import respx

from src.core.backend_client import BackendClient
from src.domains.links import LinksClient, MyServers, ReissuedKey, ServerItem

BASE = "http://backend"
SERVERS_URL = f"{BASE}/api/v1/users/my-servers/"
UPDATE_URL = f"{BASE}/api/v1/users/update-link/"


@pytest.fixture
def client() -> LinksClient:
    return LinksClient(backend=BackendClient(base_url=BASE, auth_token="t"))


@respx.mock
async def test_get_my_servers_maps_servers(client: LinksClient):
    respx.post(SERVERS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "expired_date": "2026-07-14",
                "servers": [
                    {"location": "🇳🇱 Нидерланды", "proxy_link": "tg://proxy?a=1"},
                    {"location": "🇩🇪 Германия", "proxy_link": "tg://proxy?b=2"},
                ],
            },
        )
    )

    result = await client.get_my_servers(telegram_id="42")

    assert result == MyServers(
        expired_date="2026-07-14",
        servers=[
            ServerItem(location="🇳🇱 Нидерланды", proxy_link="tg://proxy?a=1"),
            ServerItem(location="🇩🇪 Германия", proxy_link="tg://proxy?b=2"),
        ],
    )


@respx.mock
async def test_reissue_returns_key(client: LinksClient):
    respx.post(UPDATE_URL).mock(
        return_value=httpx.Response(
            200, json={"expired_date": "2026-07-14", "link": "tg://proxy?new=1"}
        )
    )

    result = await client.reissue(telegram_id="42")

    assert result == ReissuedKey(expired_date="2026-07-14", link="tg://proxy?new=1")
