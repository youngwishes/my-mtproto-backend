from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import LabeledPrice

from domains.payments.client import (
    InvoiceData,
    PaymentsClient,
    StarsInvoiceData,
    get_payments_client,
)


async def test_get_invoice_data_returns_invoice():
    mock_http = AsyncMock()
    mock_http.get.return_value = {
        "title": "BeatVault",
        "description": "MTProto proxy",
        "currency": "RUB",
        "price": 7900,
        "stars_price": 60,
        "provider_data": {"key": "value"},
        "send_email_to_provider": False,
        "need_email": False,
    }
    with patch("domains.payments.client.config") as mock_config:
        mock_config.PROVIDER_TOKEN = "test-provider"
        client = PaymentsClient(_http=mock_http)
        result = await client.get_invoice_data(telegram_id="123")

    assert isinstance(result, InvoiceData)
    assert result.title == "BeatVault"
    assert result.currency == "RUB"
    assert result.provider_token == "test-provider"
    assert len(result.prices) == 1
    assert isinstance(result.prices[0], LabeledPrice)
    assert result.prices[0].amount == 7900
    mock_http.get.assert_called_once_with(path="/api/v1/payments/", telegram_id="123")


async def test_get_stars_invoice_data_returns_stars_invoice():
    mock_http = AsyncMock()
    mock_http.get.return_value = {
        "title": "BeatVault",
        "description": "MTProto proxy",
        "stars_price": 60,
    }
    client = PaymentsClient(_http=mock_http)
    result = await client.get_stars_invoice_data(telegram_id="123")

    assert isinstance(result, StarsInvoiceData)
    assert result.currency == "XTR"
    assert result.provider_token == ""
    assert result.prices[0].amount == 60
    mock_http.get.assert_called_once_with(path="/api/v1/payments/", telegram_id="123")


async def test_record_purchase_calls_correct_endpoint():
    mock_http = AsyncMock()
    mock_http.post.return_value = {}
    client = PaymentsClient(_http=mock_http)

    await client.record_purchase(
        telegram_id=123,
        charge_id="charge_abc",
        provider="yukassa",
    )

    mock_http.post.assert_called_once_with(
        path="/api/v1/payments/buy/",
        telegram_id="123",
        data={"username": "123", "charge_id": "charge_abc", "provider": "yukassa"},
    )


def test_get_payments_client_returns_instance():
    assert isinstance(get_payments_client(), PaymentsClient)
