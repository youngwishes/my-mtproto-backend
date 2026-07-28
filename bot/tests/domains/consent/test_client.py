from __future__ import annotations

from urllib.parse import parse_qs

import httpx
import pytest
import respx

from src.core.backend_client import BackendClient
from src.domains.consent import ConsentClient, ConsentStatus
from src.exceptions import APIError

BASE = "http://backend"
STATUS_URL = f"{BASE}/api/v1/users/consent/status/"
ACCEPT_URL = f"{BASE}/api/v1/users/consent/accept/"


@pytest.fixture
def client() -> ConsentClient:
    return ConsentClient(backend=BackendClient(base_url=BASE, auth_token="t"))


@pytest.mark.parametrize("accepted", [False, True])
@respx.mock
async def test_get_status_sends_only_telegram_id_and_parses_response(
    client: ConsentClient,
    accepted: bool,
):
    route = respx.post(STATUS_URL).mock(
        return_value=httpx.Response(
            200,
            json={"legal_terms_accepted": accepted},
        )
    )

    result = await client.get_status(telegram_id="42")

    assert result == ConsentStatus(legal_terms_accepted=accepted)
    assert parse_qs(route.calls.last.request.content.decode()) == {"username": ["42"]}


@pytest.mark.parametrize("invalid_value", ["false", 0, 1])
@respx.mock
async def test_get_status_rejects_non_boolean_consent_flag(
    client: ConsentClient,
    invalid_value: str | int,
):
    respx.post(STATUS_URL).mock(
        return_value=httpx.Response(
            200,
            json={"legal_terms_accepted": invalid_value},
        )
    )

    with pytest.raises(APIError):
        await client.get_status(telegram_id="42")


@respx.mock
async def test_accept_sends_only_required_telegram_id_when_optionals_absent(
    client: ConsentClient,
):
    route = respx.post(ACCEPT_URL).mock(
        return_value=httpx.Response(
            200,
            json={"legal_terms_accepted": True},
        )
    )

    result = await client.accept(
        telegram_id="42",
        telegram_username=None,
    )

    assert result == ConsentStatus(legal_terms_accepted=True)
    assert parse_qs(route.calls.last.request.content.decode()) == {"username": ["42"]}


@respx.mock
async def test_accept_sends_telegram_username_and_valid_referrer(
    client: ConsentClient,
):
    route = respx.post(ACCEPT_URL).mock(
        return_value=httpx.Response(
            200,
            json={"legal_terms_accepted": True},
        )
    )

    await client.accept(
        telegram_id="42",
        telegram_username="bob",
        invited_from_username="777",
    )

    assert parse_qs(route.calls.last.request.content.decode()) == {
        "username": ["42"],
        "telegram_username": ["bob"],
        "invited_from_username": ["777"],
    }


@pytest.mark.parametrize(
    "response_payload",
    [
        {"legal_terms_accepted": False},
        {},
        {"legal_terms_accepted": "true"},
        {"legal_terms_accepted": 1},
        [],
    ],
    ids=["false", "missing", "string", "number", "malformed"],
)
@respx.mock
async def test_accept_rejects_response_without_exact_true_boolean(
    client: ConsentClient,
    response_payload: object,
):
    respx.post(ACCEPT_URL).mock(
        return_value=httpx.Response(200, json=response_payload)
    )

    with pytest.raises(APIError):
        await client.accept(
            telegram_id="42",
            telegram_username="bob",
        )
