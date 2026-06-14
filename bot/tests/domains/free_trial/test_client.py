from __future__ import annotations

import httpx
import pytest
import respx

from src.core.backend_client import BackendClient
from src.domains.free_trial import FreeTrialClient, FreeTrialKey

BASE = "http://backend"
CHECK_URL = f"{BASE}/api/v1/users/check-first-free-link/"
CLAIM_URL = f"{BASE}/api/v1/users/first-free-link/"


@pytest.fixture
def client() -> FreeTrialClient:
    return FreeTrialClient(backend=BackendClient(base_url=BASE, auth_token="t"))


@respx.mock
async def test_check_availability_returns_period(client: FreeTrialClient):
    route = respx.post(CHECK_URL).mock(
        return_value=httpx.Response(200, json={"available_free_period": "MONTH"})
    )

    result = await client.check_availability(telegram_id="42", telegram_username="bob")

    assert result == "MONTH"
    body = route.calls.last.request.content
    assert b"username=42" in body
    assert b"telegram_username=bob" in body


@respx.mock
async def test_check_availability_sends_referrer_when_present(client: FreeTrialClient):
    route = respx.post(CHECK_URL).mock(
        return_value=httpx.Response(200, json={"available_free_period": "TWO_WEEK"})
    )

    await client.check_availability(
        telegram_id="42", telegram_username="bob", invited_from_username="7"
    )

    assert b"invited_from_username=7" in route.calls.last.request.content


@respx.mock
async def test_check_availability_omits_referrer_when_absent(client: FreeTrialClient):
    route = respx.post(CHECK_URL).mock(
        return_value=httpx.Response(200, json={"available_free_period": "WEEK"})
    )

    await client.check_availability(telegram_id="42", telegram_username="bob")

    assert b"invited_from_username" not in route.calls.last.request.content


@respx.mock
async def test_claim_returns_key(client: FreeTrialClient):
    respx.post(CLAIM_URL).mock(
        return_value=httpx.Response(
            200, json={"expired_date": "2026-07-14"}
        )
    )

    key = await client.claim(telegram_id="42")

    assert key == FreeTrialKey(expired_date="2026-07-14")
