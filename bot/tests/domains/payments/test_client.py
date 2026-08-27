from __future__ import annotations

from dataclasses import FrozenInstanceError
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from aiogram.types import LabeledPrice

from src.core.backend_client import BackendClient
from src.domains import payments as payments_domain
from src.domains.payments import (
    ActivatedGiftCertificate,
    ApplePurchaseOutcome,
    AppleRedemptionPreview,
    AppleRedemptionResult,
    AppleStatus,
    ConfirmedPurchase,
    CryptoInvoice,
    GiftCertificate,
    HistoricalPurchaseReplay,
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
PLATEGA_INVOICE_URL = f"{BASE}/api/v1/payments/platega/invoices/"
APPLE_STATUS_URL = f"{BASE}/api/v1/payments/apples/status/"
APPLE_REDEMPTION_PREVIEW_URL = (
    f"{BASE}/api/v1/payments/apples/redemptions/preview/"
)
APPLE_REDEMPTION_CONFIRM_URL = (
    f"{BASE}/api/v1/payments/apples/redemptions/confirm/"
)

PRODUCT_JSON = {
    "title": "MTPRoto на месяц",
    "description": "Безлимитный прокси",
    "currency": "RUB",
    "price": 9900,
    "stars_price": 99,
    "rub_amount": "99.00",
    "payment_methods": ["stars", "crypto_pay"],
    "priority_payment_methods": ["crypto_pay"],
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
        rub_amount="99.00",
        payment_methods=("stars", "crypto_pay"),
        priority_payment_methods=("crypto_pay",),
    )
    assert invoice.currency == "XTR"
    assert invoice.provider_token == ""
    assert invoice.payment_methods == ("stars", "crypto_pay")
    assert invoice.priority_payment_methods == ("crypto_pay",)
    assert invoice.rub_amount == "99.00"
    assert isinstance(invoice.payment_methods, tuple)
    assert isinstance(invoice.priority_payment_methods, tuple)


@respx.mock
async def test_get_vpn_stars_invoice_uses_vpn_product(client: PaymentsClient):
    vpn_product = {
        **PRODUCT_JSON,
        "title": "VPN на месяц",
        "stars_price": 149,
        "payment_methods": ["crypto_pay"],
        "priority_payment_methods": [],
    }
    respx.get(VPN_PRODUCT_URL).mock(return_value=httpx.Response(200, json=vpn_product))

    invoice = await client.get_vpn_stars_invoice()

    assert invoice == StarsInvoice(
        title="VPN на месяц",
        description="Безлимитный прокси",
        prices=[LabeledPrice(label="VPN на месяц", amount=149)],
        rub_amount="99.00",
        payment_methods=("crypto_pay",),
        priority_payment_methods=(),
    )
    assert invoice.currency == "XTR"
    assert invoice.provider_token == ""
    assert invoice.payment_methods == ("crypto_pay",)
    assert invoice.priority_payment_methods == ()
    assert isinstance(invoice.payment_methods, tuple)
    assert isinstance(invoice.priority_payment_methods, tuple)


@respx.mock
async def test_confirm_purchase_maps_saved_loyalty_and_posts_only_payment_identity(
    client: PaymentsClient,
) -> None:
    route = respx.post(BUY_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "expired_date": "18.09.26",
                "loyalty": {
                    "apples_earned": 5,
                    "rate_percent": 5,
                    "balance": 20,
                    "eligible_purchase_count": 4,
                    "level": "Садовник",
                    "level_up": True,
                    "next_purchase_rate_percent": 10,
                },
            },
        )
    )

    result = await client.confirm_purchase(
        telegram_id=42, charge_id="ch_1", provider="stars"
    )

    assert result == ConfirmedPurchase(
        expired_date="18.09.26",
        loyalty=ApplePurchaseOutcome(
            apples_earned=5,
            rate_percent=5,
            balance=20,
            eligible_purchase_count=4,
            level="Садовник",
            level_up=True,
            next_purchase_rate_percent=10,
        ),
    )
    assert parse_qs(route.calls.last.request.content) == {
        b"username": [b"42"],
        b"charge_id": [b"ch_1"],
        b"provider": [b"stars"],
    }
    assert route.calls.last.request.headers["Bot-Auth-Token"] == "t"


@respx.mock
async def test_confirm_purchase_maps_exact_historical_tag(
    client: PaymentsClient,
) -> None:
    respx.post(BUY_URL).mock(
        return_value=httpx.Response(200, json={"kind": "historical_replay"})
    )

    result = await client.confirm_purchase(
        telegram_id=42,
        charge_id="historical_charge",
        provider="stars",
    )

    assert result == HistoricalPurchaseReplay()


@respx.mock
async def test_confirm_gift_certificate_purchase_returns_code(client: PaymentsClient):
    route = respx.post(GIFT_BUY_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": "KEY-ABCD-1234",
                "loyalty": {
                    "apples_earned": 10,
                    "rate_percent": 10,
                    "balance": 27,
                    "eligible_purchase_count": 6,
                    "level": "Садовник",
                    "level_up": False,
                    "next_purchase_rate_percent": 10,
                },
            },
        )
    )

    result = await client.confirm_gift_certificate_purchase(
        telegram_id=42,
        charge_id="gift_ch_1",
        provider="stars",
    )

    assert result == GiftCertificate(
        code="KEY-ABCD-1234",
        loyalty=ApplePurchaseOutcome(
            apples_earned=10,
            rate_percent=10,
            balance=27,
            eligible_purchase_count=6,
            level="Садовник",
            level_up=False,
            next_purchase_rate_percent=10,
        ),
    )
    assert parse_qs(route.calls.last.request.content) == {
        b"username": [b"42"],
        b"charge_id": [b"gift_ch_1"],
        b"provider": [b"stars"],
    }
    assert route.calls.last.request.headers["Bot-Auth-Token"] == "t"


@respx.mock
async def test_confirm_gift_certificate_purchase_maps_exact_historical_tag(
    client: PaymentsClient,
) -> None:
    respx.post(GIFT_BUY_URL).mock(
        return_value=httpx.Response(200, json={"kind": "historical_replay"})
    )

    result = await client.confirm_gift_certificate_purchase(
        telegram_id=42,
        charge_id="historical_gift",
        provider="stars",
    )

    assert result == HistoricalPurchaseReplay()


@respx.mock
async def test_get_apple_status_posts_only_username_and_maps_frozen_snapshot(
    client: PaymentsClient,
) -> None:
    route = respx.post(APPLE_STATUS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "balance": 37,
                "eligible_purchase_count": 4,
                "level": "Садовник",
                "rate_percent": 10,
                "next_level_purchase_count": 7,
                "purchases_to_next_level": 3,
                "is_max_level": False,
                "redeemable_days": 2,
                "missing_apples": 0,
                "has_existing_key": True,
            },
        )
    )

    result = await client.get_apple_status(telegram_id=42)

    assert result == AppleStatus(
        balance=37,
        eligible_purchase_count=4,
        level="Садовник",
        rate_percent=10,
        next_level_purchase_count=7,
        purchases_to_next_level=3,
        is_max_level=False,
        redeemable_days=2,
        missing_apples=0,
        has_existing_key=True,
    )
    assert parse_qs(route.calls.last.request.content) == {b"username": [b"42"]}
    assert route.calls.last.request.headers["Bot-Auth-Token"] == "t"
    with pytest.raises(FrozenInstanceError):
        result.balance = 999  # type: ignore[misc]


@respx.mock
async def test_preview_apple_redemption_posts_only_username_and_mode(
    client: PaymentsClient,
) -> None:
    route = respx.post(APPLE_REDEMPTION_PREVIEW_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "confirmation_id": 17,
                "mode": "all",
                "apples_spent": 30,
                "days": 2,
                "projected_expired_date": "21.08.26",
            },
        )
    )

    result = await client.preview_apple_redemption(telegram_id=42, mode="all")

    assert result == AppleRedemptionPreview(
        confirmation_id=17,
        mode="all",
        apples_spent=30,
        days=2,
        projected_expired_date="21.08.26",
    )
    assert parse_qs(route.calls.last.request.content) == {
        b"username": [b"42"],
        b"mode": [b"all"],
    }
    assert route.calls.last.request.headers["Bot-Auth-Token"] == "t"


@respx.mock
async def test_confirm_apple_redemption_posts_only_username_and_confirmation_id(
    client: PaymentsClient,
) -> None:
    route = respx.post(APPLE_REDEMPTION_CONFIRM_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "apples_spent": 30,
                "days": 2,
                "expired_date": "21.08.26",
                "balance": 7,
            },
        )
    )

    result = await client.confirm_apple_redemption(
        telegram_id=42,
        confirmation_id=17,
    )

    assert result == AppleRedemptionResult(
        apples_spent=30,
        days=2,
        expired_date="21.08.26",
        balance=7,
    )
    assert parse_qs(route.calls.last.request.content) == {
        b"username": [b"42"],
        b"confirmation_id": [b"17"],
    }
    assert route.calls.last.request.headers["Bot-Auth-Token"] == "t"


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


@respx.mock
async def test_create_platega_invoice_posts_only_identity_and_kind(
    client: PaymentsClient,
) -> None:
    route = respx.post(PLATEGA_INVOICE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "payment_url": "https://pay.example/invoice/opaque",
                "rub_amount": "99.50",
                "expires_at": "2026-08-08T12:15:00Z",
                "reused": True,
            },
        )
    )

    result = await client.create_platega_invoice(
        telegram_id=42,
        purchase_kind="gift_certificate",
    )

    assert result == payments_domain.PlategaInvoice(
        payment_url="https://pay.example/invoice/opaque",
        rub_amount="99.50",
        expires_at="2026-08-08T12:15:00Z",
        reused=True,
    )
    assert parse_qs(route.calls.last.request.content) == {
        b"username": [b"42"],
        b"purchase_kind": [b"gift_certificate"],
    }
    assert route.calls.last.request.headers["Bot-Auth-Token"] == "t"
