from __future__ import annotations

import json

import httpx
import pytest
import respx
from aiogram.types import LabeledPrice

from src.core.backend_client import BackendClient
from src.domains.payments import CardInvoice, PaymentsClient, StarsInvoice

BASE = "http://backend"
PRODUCT_URL = f"{BASE}/api/v1/payments/"
BUY_URL = f"{BASE}/api/v1/payments/buy/"

PRODUCT_JSON = {
    "title": "MTPRoto на месяц",
    "description": "Безлимитный прокси",
    "currency": "RUB",
    "provider_data": {"receipt": {"items": []}},
    "send_email_to_provider": False,
    "need_email": False,
    "price": 9900,
    "stars_price": 80,
}


@pytest.fixture
def client() -> PaymentsClient:
    return PaymentsClient(
        backend=BackendClient(base_url=BASE, auth_token="t"),
        provider_token="PROVIDER-XYZ",
    )


@respx.mock
async def test_get_card_invoice_maps_fields(client: PaymentsClient):
    respx.get(PRODUCT_URL).mock(return_value=httpx.Response(200, json=PRODUCT_JSON))

    invoice = await client.get_card_invoice()

    assert invoice == CardInvoice(
        title="MTPRoto на месяц",
        description="Безлимитный прокси",
        currency="RUB",
        provider_data=json.dumps({"receipt": {"items": []}}),
        send_email_to_provider=False,
        need_email=False,
        prices=[LabeledPrice(label="MTPRoto на месяц", amount=9900)],
        provider_token="PROVIDER-XYZ",
    )


@respx.mock
async def test_card_invoice_asdict_has_send_invoice_kwargs(client: PaymentsClient):
    respx.get(PRODUCT_URL).mock(return_value=httpx.Response(200, json=PRODUCT_JSON))

    invoice = await client.get_card_invoice()

    assert set(invoice.asdict()) == {
        "title",
        "description",
        "currency",
        "provider_data",
        "send_email_to_provider",
        "need_email",
        "prices",
        "provider_token",
    }


@respx.mock
async def test_get_stars_invoice_maps_fields(client: PaymentsClient):
    respx.get(PRODUCT_URL).mock(return_value=httpx.Response(200, json=PRODUCT_JSON))

    invoice = await client.get_stars_invoice()

    assert invoice == StarsInvoice(
        title="MTPRoto на месяц",
        description="Безлимитный прокси",
        prices=[LabeledPrice(label="MTPRoto на месяц", amount=80)],
    )
    assert invoice.currency == "XTR"
    assert invoice.provider_token == ""


@respx.mock
async def test_confirm_purchase_posts_charge(client: PaymentsClient):
    route = respx.post(BUY_URL).mock(return_value=httpx.Response(200))

    result = await client.confirm_purchase(
        telegram_id=42, charge_id="ch_1", provider="stars"
    )

    assert result is None
    body = route.calls.last.request.content
    assert b"username=42" in body
    assert b"charge_id=ch_1" in body
    assert b"provider=stars" in body
