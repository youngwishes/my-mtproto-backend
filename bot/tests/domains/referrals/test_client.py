from __future__ import annotations

from unittest.mock import AsyncMock

from domains.referrals.client import (
    ReferralCabinet,
    ReferralLink,
    ReferralsClient,
    get_referrals_client,
)


async def test_get_cabinet_returns_cabinet():
    mock_http = AsyncMock()
    mock_http.post.return_value = {
        "total_referrals_count": 10,
        "active_referrals_count": 5,
        "referral_link": "https://t.me/bot?start=123",
        "link_activated_count": 3,
    }
    client = ReferralsClient(_http=mock_http)
    result = await client.get_cabinet(telegram_id="123")

    assert isinstance(result, ReferralCabinet)
    assert result.active_referrals_count == 5
    assert result.referral_link == "https://t.me/bot?start=123"
    mock_http.post.assert_called_once_with(
        path="/api/v1/users/referral/cabinet/",
        telegram_id="123",
        data={"username": "123"},
    )


async def test_get_referral_link_returns_link():
    mock_http = AsyncMock()
    mock_http.post.return_value = {
        "link": "https://t.me/proxy?server=1.2.3.4",
        "expired_date": "2026-07-11",
    }
    client = ReferralsClient(_http=mock_http)
    result = await client.get_referral_link(telegram_id="123")

    assert isinstance(result, ReferralLink)
    assert result.link == "https://t.me/proxy?server=1.2.3.4"
    mock_http.post.assert_called_once_with(
        path="/api/v1/users/referral/link/",
        telegram_id="123",
        data={"username": "123"},
    )


def test_get_referrals_client_returns_instance():
    assert isinstance(get_referrals_client(), ReferralsClient)
