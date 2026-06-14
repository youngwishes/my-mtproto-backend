from __future__ import annotations

import httpx
import pytest
import respx

from src.core.backend_client import BackendClient
from src.domains.referrals import ReferralCabinet, ReferralRewardKey, ReferralsClient

BASE = "http://backend"
CABINET_URL = f"{BASE}/api/v1/users/referral/cabinet/"
REWARD_URL = f"{BASE}/api/v1/users/referral/link/"


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
                "link_activated_count": 1,
            },
        )
    )

    result = await client.get_cabinet(telegram_id="42")

    assert result == ReferralCabinet(
        total_referrals_count=7,
        active_referrals_count=5,
        referral_link="https://t.me/bot?start=42",
        link_activated_count=1,
    )


@respx.mock
async def test_claim_reward_returns_key(client: ReferralsClient):
    respx.post(REWARD_URL).mock(
        return_value=httpx.Response(
            200, json={"expired_date": "2026-06-28"}
        )
    )

    result = await client.claim_reward(telegram_id="42")

    assert result == ReferralRewardKey(
        expired_date="2026-06-28"
    )
