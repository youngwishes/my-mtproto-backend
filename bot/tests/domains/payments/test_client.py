from __future__ import annotations

from urllib.parse import parse_qs

import httpx
import pytest
import respx
from aiogram.types import LabeledPrice

from src.core.backend_client import BackendClient
from src.domains.payments import (
    ActivatedGiftCertificate,
    CryptoInvoice,
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
CRYPTO_INVOICE_URL = f"{BASE}/api/v1/payments/crypto/invoices/"

PRODUCT_JSON = {
    "title": "MTPRoto на месяц",
    "description": "Безлимитный прокси",
    "currency": "RUB",
    "provider_data": {"receipt": {"items": []}},
    "send_email_to_provider": False,
    "need_email": False,
    "price": 9900,
    "stars_price": 99,
    "payment_methods": ["stars", "crypto_pay"],
}

@pytest.fixture
def client() -> PaymentsClient:
    return PaymentsClient(
        backend=BackendClient(base_url=BASE, auth_token="t"),
    )


@respx.mock
async def test_get_stars_invoice_maps_fields(client: PaymentsClient):
    respx.get(PRODUCT_URL).mock(return_value=httpx.Response(200, json=PRODUCT_JSON))

    invoice = await client.get_stars_invoice()

    assert invoice == StarsInvoice(
        title="MTPRoto на месяц",
        description="Безлимитный прокси",
        prices=[LabeledPrice(label="MTPRoto на месяц", amount=99)],
        payment_methods=("stars", "crypto_pay"),
    )
    assert invoice.currency == "XTR"
    assert invoice.provider_token == ""
    assert invoice.payment_methods == ("stars", "crypto_pay")
    assert isinstance(invoice.payment_methods, tuple)


@respx.mock
async def test_get_vpn_stars_invoice_uses_vpn_product(client: PaymentsClient):
    vpn_product = {
        **PRODUCT_JSON,
        "title": "VPN на месяц",
        "stars_price": 149,
        "payment_methods": ["crypto_pay"],
    }
    respx.get(VPN_PRODUCT_URL).mock(return_value=httpx.Response(200, json=vpn_product))

    invoice = await client.get_vpn_stars_invoice()

    assert invoice.title == "VPN на месяц"
    assert invoice.prices == [LabeledPrice(label="VPN на месяц", amount=149)]
    assert invoice.payment_methods == ("crypto_pay",)
    assert isinstance(invoice.payment_methods, tuple)


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


@respx.mock
async def test_create_crypto_invoice_posts_kind_and_maps_exact_decimal_string(
    client: PaymentsClient,
) -> None:
    route = respx.post(CRYPTO_INVOICE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "invoice_url": "https://t.me/CryptoBot?start=x",
                "rub_amount": "99.00",
                "expires_at": "2026-08-02T12:30:00Z",
                "reused": False,
            },
        )
    )

    result = await client.create_crypto_invoice(
        telegram_id=42,
        purchase_kind="subscription",
    )

    assert result == CryptoInvoice(
        invoice_url="https://t.me/CryptoBot?start=x",
        rub_amount="99.00",
        expires_at="2026-08-02T12:30:00Z",
        reused=False,
    )
    assert parse_qs(route.calls.last.request.content) == {
        b"username": [b"42"],
        b"purchase_kind": [b"subscription"],
    }
    assert route.calls.last.request.headers["Bot-Auth-Token"] == "t"
