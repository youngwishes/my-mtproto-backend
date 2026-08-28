from __future__ import annotations

import httpx
import pytest
import respx

from src.core.backend_client import BackendClient
from src.domains.referrals import ReferralCabinet, ReferralsClient

BASE = "http://backend"
CABINET_URL = f"{BASE}/api/v1/users/referral/cabinet/"


@pytest.fixture
def client() -> ReferralsClient:
    return ReferralsClient(backend=BackendClient(base_url=BASE, auth_token="t"))


@respx.mock
async def test_get_cabinet_maps_fields(client: ReferralsClient):
    respx.post(CABINET_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "total_referrals_count": 7,
                "active_referrals_count": 5,
                "referral_link": "https://t.me/bot?start=42",
                "apple_balance": 45,
            },
        )
    )

    result = await client.get_cabinet(telegram_id="42")

    assert result == ReferralCabinet(
        total_referrals_count=7,
        active_referrals_count=5,
        referral_link="https://t.me/bot?start=42",
        apple_balance=45,
    )
