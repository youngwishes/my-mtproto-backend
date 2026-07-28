from __future__ import annotations

import httpx
import pytest
import respx

from src.core.backend_client import BackendClient
from src.domains.free_trial import FreeTrialClient, FreeTrialKey
from src.exceptions import APIError

BASE = "http://backend"
CHECK_URL = f"{BASE}/api/v1/users/check-first-free-link/"
CLAIM_URL = f"{BASE}/api/v1/users/first-free-link/"
CONSENT_STATUS_URL = f"{BASE}/api/v1/users/consent/status/"
CONSENT_ACCEPT_URL = f"{BASE}/api/v1/users/consent/accept/"


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
async def test_check_availability_omits_telegram_username_when_none(
    client: FreeTrialClient,
):
    route = respx.post(CHECK_URL).mock(
        return_value=httpx.Response(200, json={"available_free_period": "WEEK"})
    )

    await client.check_availability(telegram_id="42", telegram_username=None)

    body = route.calls.last.request.content
    assert b"telegram_username" not in body
    assert b"None" not in body


@respx.mock
async def test_claim_returns_key(client: FreeTrialClient):
    respx.post(CLAIM_URL).mock(
        return_value=httpx.Response(
            200, json={"expired_date": "2026-07-14"}
        )
    )

    key = await client.claim(telegram_id="42")

    assert key == FreeTrialKey(expired_date="2026-07-14")


@respx.mock
async def test_get_consent_status_sends_only_telegram_id(client: FreeTrialClient):
    route = respx.post(CONSENT_STATUS_URL).mock(
        return_value=httpx.Response(200, json={"legal_terms_accepted": False})
    )

    result = await client.get_consent_status(telegram_id="42")

    assert result is False
    assert route.calls.last.request.content == b"username=42"


@respx.mock
async def test_accept_consent_sends_user_data(client: FreeTrialClient):
    route = respx.post(CONSENT_ACCEPT_URL).mock(
        return_value=httpx.Response(200, json={"legal_terms_accepted": True})
    )

    result = await client.accept_consent(
        telegram_id="42",
        telegram_username="bob",
        invited_from_username="777",
    )

    assert result is True
    body = route.calls.last.request.content
    assert b"username=42" in body
    assert b"telegram_username=bob" in body
    assert b"invited_from_username=777" in body


@pytest.mark.parametrize(
    "payload",
    [None, [], "false", {}, {"legal_terms_accepted": "false"}, {"legal_terms_accepted": 0}],
)
@respx.mock
async def test_get_consent_status_rejects_malformed_response(
    client: FreeTrialClient,
    payload,
):
    respx.post(CONSENT_STATUS_URL).mock(
        return_value=httpx.Response(200, json=payload)
    )

    with pytest.raises(APIError):
        await client.get_consent_status(telegram_id="42")


@respx.mock
async def test_accept_consent_rejects_false_response(client: FreeTrialClient):
    respx.post(CONSENT_ACCEPT_URL).mock(
        return_value=httpx.Response(200, json={"legal_terms_accepted": False})
    )

    with pytest.raises(APIError):
        await client.accept_consent(
            telegram_id="42",
            telegram_username=None,
        )
