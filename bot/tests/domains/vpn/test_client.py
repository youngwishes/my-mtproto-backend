from __future__ import annotations

import httpx
import pytest
import respx

from src.core.backend_client import BackendClient
from src.domains.vpn import VPNClient, VPNMenu, VPNPurchase

BASE = "http://backend"
MENU_URL = f"{BASE}/api/v1/vpn/menu/?username=42"
BUY_URL = f"{BASE}/api/v1/vpn/payments/buy/"


@pytest.fixture
def client() -> VPNClient:
    return VPNClient(backend=BackendClient(base_url=BASE, auth_token="t"))


@respx.mock
async def test_get_menu_maps_exact_backend_state(client: VPNClient):
    respx.get(MENU_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "active",
                "expired_at": "2026-08-31T12:00:00+00:00",
                "subscription_url": "https://vpn.example/subscriptions/token/",
            },
        )
    )

    menu = await client.get_menu(telegram_id=42)

    assert menu == VPNMenu(
        status="active",
        expired_at="2026-08-31T12:00:00+00:00",
        subscription_url="https://vpn.example/subscriptions/token/",
    )


@respx.mock
async def test_confirm_purchase_posts_only_vpn_payment_data(client: VPNClient):
    route = respx.post(BUY_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "expired_at": "2026-08-31T12:00:00+00:00",
                "subscription_url": "https://vpn.example/subscriptions/token/",
            },
        )
    )

    purchase = await client.confirm_purchase(
        telegram_id=42,
        charge_id="vpn_charge_1",
        provider="stars",
    )

    assert purchase == VPNPurchase(
        expired_at="2026-08-31T12:00:00+00:00",
        subscription_url="https://vpn.example/subscriptions/token/",
    )
    body = route.calls.last.request.content
    assert b"username=42" in body
    assert b"charge_id=vpn_charge_1" in body
    assert b"provider=stars" in body
    assert b"product_code=vpn_30d" in body
