from __future__ import annotations

import pytest
import httpx
import respx

from core.backend_client import BackendClient
from core.exceptions import APIError


@respx.mock
async def test_post_returns_json_on_success():
    respx.post("http://test.api/api/v1/users/test/").mock(
        return_value=httpx.Response(200, json={"available_free_period": "MONTH"})
    )
    client = BackendClient()
    result = await client.post(
        path="/api/v1/users/test/",
        telegram_id="123",
        data={"username": "123"},
    )
    assert result == {"available_free_period": "MONTH"}


@respx.mock
async def test_post_sends_auth_header():
    route = respx.post("http://test.api/api/v1/users/test/").mock(
        return_value=httpx.Response(200, json={})
    )
    await BackendClient().post(
        path="/api/v1/users/test/",
        telegram_id="123",
        data={},
    )
    assert route.calls[0].request.headers["bot-auth-token"] == "test-bot-auth"


@respx.mock
async def test_post_raises_api_error_with_message_on_http_error_with_body():
    respx.post("http://test.api/api/v1/users/test/").mock(
        return_value=httpx.Response(400, json={"error": "user not found"})
    )
    with pytest.raises(APIError) as exc_info:
        await BackendClient().post(
            path="/api/v1/users/test/",
            telegram_id="123",
            data={},
        )
    assert exc_info.value.message == "user not found"
    assert exc_info.value.telegram_id == "123"


@respx.mock
async def test_post_raises_api_error_without_message_on_network_error():
    respx.post("http://test.api/api/v1/users/test/").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    with pytest.raises(APIError) as exc_info:
        await BackendClient().post(
            path="/api/v1/users/test/",
            telegram_id="123",
            data={},
        )
    assert exc_info.value.telegram_id == "123"


@respx.mock
async def test_get_returns_json_on_success():
    respx.get("http://test.api/api/v1/payments/").mock(
        return_value=httpx.Response(200, json={"title": "BeatVault", "price": 7900})
    )
    client = BackendClient()
    result = await client.get(path="/api/v1/payments/")
    assert result == {"title": "BeatVault", "price": 7900}


@respx.mock
async def test_get_sends_auth_header():
    route = respx.get("http://test.api/api/v1/payments/").mock(
        return_value=httpx.Response(200, json={})
    )
    await BackendClient().get(path="/api/v1/payments/")
    assert route.calls[0].request.headers["bot-auth-token"] == "test-bot-auth"


@respx.mock
async def test_get_raises_api_error_with_message_on_http_error_with_body():
    respx.get("http://test.api/api/v1/payments/").mock(
        return_value=httpx.Response(400, json={"error": "not found"})
    )
    with pytest.raises(APIError) as exc_info:
        await BackendClient().get(path="/api/v1/payments/")
    assert exc_info.value.message == "not found"


@respx.mock
async def test_get_raises_api_error_on_network_error():
    respx.get("http://test.api/api/v1/payments/").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    with pytest.raises(APIError):
        await BackendClient().get(path="/api/v1/payments/")
