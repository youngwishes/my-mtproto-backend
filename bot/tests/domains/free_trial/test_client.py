from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from domains.free_trial.client import FreeLink, FreeTrialClient, get_free_trial_client


async def test_check_eligibility_returns_available_period():
    mock_http = AsyncMock()
    mock_http.post.return_value = {"available_free_period": "MONTH"}
    client = FreeTrialClient(_http=mock_http)

    result = await client.check_eligibility(
        telegram_id="123",
        telegram_username="testuser",
    )

    assert result == "MONTH"
    mock_http.post.assert_called_once_with(
        path="/api/v1/users/check-first-free-link/",
        telegram_id="123",
        data={"username": "123", "telegram_username": "testuser"},
    )


async def test_check_eligibility_includes_referrer_when_provided():
    mock_http = AsyncMock()
    mock_http.post.return_value = {"available_free_period": "TWO_WEEK"}
    client = FreeTrialClient(_http=mock_http)

    await client.check_eligibility(
        telegram_id="123",
        telegram_username="testuser",
        invited_from_username="456",
    )

    call_data = mock_http.post.call_args.kwargs["data"]
    assert call_data["invited_from_username"] == "456"


async def test_activate_returns_free_link():
    mock_http = AsyncMock()
    mock_http.post.return_value = {
        "link": "https://t.me/proxy?server=1.2.3.4",
        "expired_date": "2026-07-11",
    }
    client = FreeTrialClient(_http=mock_http)

    result = await client.activate(telegram_id="123")

    assert isinstance(result, FreeLink)
    assert result.link == "https://t.me/proxy?server=1.2.3.4"
    assert result.expired_date == "2026-07-11"


def test_get_free_trial_client_returns_instance():
    client = get_free_trial_client()
    assert isinstance(client, FreeTrialClient)
