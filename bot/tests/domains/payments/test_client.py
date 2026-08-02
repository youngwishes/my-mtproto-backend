from __future__ import annotations

import json

import httpx
import pytest
import respx
from aiogram.types import LabeledPrice

from src.core.backend_client import BackendClient
from src.domains.payments import (
    ActivatedGiftCertificate,
    CardInvoice,
    GiftCertificate,
    PaymentsClient,
    StarsInvoice,
)

BASE = "http://backend"
PRODUCT_URL = f"{BASE}/api/v1/payments/"
VPN_PRODUCT_URL = f"{BASE}/api/v1/payments/products/vpn_30d/"
BUY_URL = f"{BASE}/api/v1/payments/buy/"
GIFT_BUY_URL = f"{BASE}/api/v1/payments/gift-certificates/buy/"
GIFT_ACTIVATE_URL = f"{BASE}/api/v1/payments/gift-certificates/activate/"

PRODUCT_JSON = {
    "title": "MTPRoto на месяц",
    "description": "Безлимитный прокси",
    "currency": "RUB",
    "provider_data": {"receipt": {"items": []}},
    "send_email_to_provider": False,
    "need_email": False,
    "price": 9900,
    "stars_price": 99,
}

VPN_PROVIDER_DATA = {
    "receipt": {
        "customer": {},
        "items": [
            {
                "description": "Оплата VPN-подписки на один месяц.",
                "quantity": "1.00",
                "amount": {"value": 149, "currency": "RUB"},
                "vat_code": 4,
                "payment_mode": "full_payment",
            },
        ],
    }
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
        prices=[LabeledPrice(label="MTPRoto на месяц", amount=99)],
    )
    assert invoice.currency == "XTR"
    assert invoice.provider_token == ""


@respx.mock
async def test_get_vpn_card_invoice_uses_vpn_product(client: PaymentsClient):
    vpn_product = {
        **PRODUCT_JSON,
        "title": "VPN на 30 дней",
        "provider_data": VPN_PROVIDER_DATA,
        "send_email_to_provider": True,
        "need_email": True,
        "price": 14900,
    }
    respx.get(VPN_PRODUCT_URL).mock(return_value=httpx.Response(200, json=vpn_product))

    invoice = await client.get_vpn_card_invoice()

    assert invoice == CardInvoice(
        title="VPN на 30 дней",
        description="Безлимитный прокси",
        currency="RUB",
        provider_data=json.dumps(VPN_PROVIDER_DATA),
        send_email_to_provider=True,
        need_email=True,
        prices=[LabeledPrice(label="VPN на 30 дней", amount=14900)],
        provider_token="PROVIDER-XYZ",
    )


@respx.mock
async def test_get_vpn_stars_invoice_uses_vpn_product(client: PaymentsClient):
    vpn_product = {**PRODUCT_JSON, "title": "VPN на месяц", "stars_price": 149}
    respx.get(VPN_PRODUCT_URL).mock(return_value=httpx.Response(200, json=vpn_product))

    invoice = await client.get_vpn_stars_invoice()

    assert invoice.title == "VPN на месяц"
    assert invoice.prices == [LabeledPrice(label="VPN на месяц", amount=149)]


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


@respx.mock
async def test_confirm_gift_certificate_purchase_returns_code(client: PaymentsClient):
    route = respx.post(GIFT_BUY_URL).mock(
        return_value=httpx.Response(200, json={"code": "KEY-ABCD-1234"})
    )

    result = await client.confirm_gift_certificate_purchase(
        telegram_id=42,
        charge_id="gift_ch_1",
        provider="yukassa",
    )

    assert result == GiftCertificate(code="KEY-ABCD-1234")
    body = route.calls.last.request.content
    assert b"username=42" in body
    assert b"charge_id=gift_ch_1" in body
    assert b"provider=yukassa" in body


@respx.mock
async def test_activate_gift_certificate_posts_code(client: PaymentsClient):
    route = respx.post(GIFT_ACTIVATE_URL).mock(
        return_value=httpx.Response(200, json={"expired_date": "08.08.26"})
    )

    result = await client.activate_gift_certificate(
        telegram_id=42,
        code=" key-abcd-1234 ",
    )

    assert result == ActivatedGiftCertificate(expired_date="08.08.26")
    body = route.calls.last.request.content
    assert b"username=42" in body
    assert b"code=+key-abcd-1234+" in body
