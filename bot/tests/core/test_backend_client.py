from __future__ import annotations

import httpx
import pytest
import respx

from src.core.backend_client import BackendClient
from src.exceptions import APIError

BASE = "http://backend"


@pytest.fixture
def client() -> BackendClient:
    return BackendClient(base_url=BASE, auth_token="secret")


@respx.mock
async def test_post_returns_json_payload(client: BackendClient):
    respx.post(f"{BASE}/api/v1/x/").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    result = await client.post("/api/v1/x/", data={"username": "42"})

    assert result == {"ok": True}


@respx.mock
async def test_post_sends_auth_header_and_form_body(client: BackendClient):
    route = respx.post(f"{BASE}/api/v1/x/").mock(
        return_value=httpx.Response(200, json={})
    )

    await client.post("/api/v1/x/", data={"username": "42"})

    request = route.calls.last.request
    assert request.headers["Bot-Auth-Token"] == "secret"
    assert b"username=42" in request.content


@respx.mock
async def test_post_raises_apierror_with_backend_message_on_error_status(
    client: BackendClient,
):
    respx.post(f"{BASE}/api/v1/x/").mock(
        return_value=httpx.Response(400, json={"error": "Вы уже получали ссылку"})
    )

    with pytest.raises(APIError) as exc_info:
        await client.post("/api/v1/x/", data={}, telegram_id="42")

    assert exc_info.value.message == "Вы уже получали ссылку"
    assert exc_info.value.telegram_id == "42"
    assert exc_info.value.context["request_url"] == f"{BASE}/api/v1/x/"


@respx.mock
async def test_post_falls_back_to_docstring_when_error_body_not_json(
    client: BackendClient,
):
    respx.post(f"{BASE}/api/v1/x/").mock(
        return_value=httpx.Response(500, text="upstream exploded")
    )

    with pytest.raises(APIError) as exc_info:
        await client.post("/api/v1/x/", data={}, telegram_id="42")

    assert exc_info.value.message == APIError.__doc__


@respx.mock
async def test_post_raises_apierror_on_connection_failure(client: BackendClient):
    respx.post(f"{BASE}/api/v1/x/").mock(side_effect=httpx.ConnectError("boom"))

    with pytest.raises(APIError) as exc_info:
        await client.post("/api/v1/x/", data={}, telegram_id="42")

    assert exc_info.value.telegram_id == "42"


@respx.mock
async def test_post_without_json_returns_empty_dict_on_empty_body(
    client: BackendClient,
):
    respx.post(f"{BASE}/api/v1/buy/").mock(return_value=httpx.Response(200))

    result = await client.post("/api/v1/buy/", data={}, expect_json=False)

    assert result == {}


@respx.mock
async def test_post_without_json_still_raises_on_error_status(client: BackendClient):
    respx.post(f"{BASE}/api/v1/buy/").mock(
        return_value=httpx.Response(402, json={"error": "no money"})
    )

    with pytest.raises(APIError) as exc_info:
        await client.post("/api/v1/buy/", data={}, telegram_id="42", expect_json=False)

    assert exc_info.value.message == "no money"


@respx.mock
async def test_get_returns_json_payload(client: BackendClient):
    route = respx.get(f"{BASE}/api/v1/payments/").mock(
        return_value=httpx.Response(200, json={"title": "Подписка"})
    )

    result = await client.get("/api/v1/payments/")

    assert result == {"title": "Подписка"}
    assert route.calls.last.request.headers["Bot-Auth-Token"] == "secret"
