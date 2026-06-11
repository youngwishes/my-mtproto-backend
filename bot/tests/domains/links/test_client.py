from __future__ import annotations

from unittest.mock import AsyncMock

from domains.links.client import LinksClient, UpdatedLink, get_links_client


async def test_update_returns_updated_link():
    mock_http = AsyncMock()
    mock_http.post.return_value = {
        "link": "https://t.me/proxy?server=1.2.3.4",
        "expired_date": "2026-07-11",
    }
    client = LinksClient(_http=mock_http)
    result = await client.update(telegram_id="123")

    assert isinstance(result, UpdatedLink)
    assert result.link == "https://t.me/proxy?server=1.2.3.4"
    assert result.expired_date == "2026-07-11"
    mock_http.post.assert_called_once_with(
        path="/api/v1/users/update-link/",
        telegram_id="123",
        data={"username": "123"},
    )


def test_get_links_client_returns_instance():
    assert isinstance(get_links_client(), LinksClient)
