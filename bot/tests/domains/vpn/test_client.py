from __future__ import annotations

import json

import httpx
import respx
from aiogram.types import LabeledPrice

from src.core.backend_client import BackendClient
from src.domains.vpn import (
    VPNAccessStatus,
    VPNClient,
    VPNInvoice,
    VPNPaymentReceiptStatus,
)

BASE = "http://backend"
PAYLOAD = "a" * 64


def _client(*, sales_enabled: bool = True) -> VPNClient:
    return VPNClient(
        backend=BackendClient(base_url=BASE, auth_token="secret"),
        provider_token="provider-token",
        sales_enabled=sales_enabled,
    )


@respx.mock
async def test_create_rub_invoice_maps_exact_backend_intent() -> None:
    route = respx.post(f"{BASE}/api/v1/vpn/payment-intents/").mock(
        return_value=httpx.Response(
            200,
            json={
                "title": "VLESS VPN — 30 дней",
                "description": "Персональная VPN-подписка на 30 дней",
                "invoice_payload": PAYLOAD,
                "currency": "RUB",
                "provider": "yukassa",
                "provider_data": {"receipt": {"items": []}},
                "send_email_to_provider": True,
                "need_email": True,
                "price": 19900,
                "expires_at": "2026-07-16T12:15:00+03:00",
            },
        )
    )

    result = await _client().create_invoice(telegram_id=42, currency="RUB")

    assert result == VPNInvoice(
        title="VLESS VPN — 30 дней",
        description="Персональная VPN-подписка на 30 дней",
        invoice_payload=PAYLOAD,
        currency="RUB",
        provider="yukassa",
        prices=[LabeledPrice(label="VLESS VPN — 30 дней", amount=19900)],
        expires_at="2026-07-16T12:15:00+03:00",
        provider_token="provider-token",
        provider_data=json.dumps({"receipt": {"items": []}}),
        send_email_to_provider=True,
        need_email=True,
    )
    assert route.calls.last.request.content == b"username=42&currency=RUB"


@respx.mock
async def test_create_stars_invoice_has_empty_provider_token() -> None:
    respx.post(f"{BASE}/api/v1/vpn/payment-intents/").mock(
        return_value=httpx.Response(
            200,
            json={
                "title": "VLESS VPN — 30 дней",
                "description": "Персональная VPN-подписка на 30 дней",
                "invoice_payload": PAYLOAD,
                "currency": "XTR",
                "provider": "stars",
                "stars_price": 150,
                "expires_at": "2026-07-16T12:15:00+03:00",
            },
        )
    )

    result = await _client().create_invoice(telegram_id="42", currency="XTR")

    assert result.currency == "XTR"
    assert result.provider == "stars"
    assert result.provider_token == ""
    assert result.prices == [LabeledPrice(label=result.title, amount=150)]
    assert result.invoice_payload == PAYLOAD


@respx.mock
async def test_pre_checkout_passes_payload_currency_and_amount_unchanged() -> None:
    route = respx.post(f"{BASE}/api/v1/vpn/pre-checkout/").mock(
        return_value=httpx.Response(200, json={"status": "APPROVED"})
    )

    await _client().approve_pre_checkout(
        telegram_id=42,
        invoice_payload=PAYLOAD,
        currency="RUB",
        amount=19900,
    )

    assert route.calls.last.request.content == (
        f"username=42&invoice_payload={PAYLOAD}&currency=RUB&amount=19900".encode()
    )


@respx.mock
async def test_accept_payment_returns_typed_status_and_exact_request() -> None:
    route = respx.post(f"{BASE}/api/v1/vpn/payments/").mock(
        return_value=httpx.Response(202, json={"status": "ACCEPTED"})
    )

    result = await _client().accept_payment(
        telegram_id=42,
        invoice_payload=PAYLOAD,
        provider="yukassa",
        charge_id="charge-1",
        currency="RUB",
        amount=19900,
    )

    assert result is VPNPaymentReceiptStatus.ACCEPTED
    assert route.calls.last.request.content == (
        f"username=42&invoice_payload={PAYLOAD}&provider=yukassa&charge_id=charge-1&currency=RUB&amount=19900".encode()
    )


@respx.mock
async def test_status_and_reissue_are_available_when_sales_disabled() -> None:
    client = _client(sales_enabled=False)
    respx.post(f"{BASE}/api/v1/vpn/status/").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "READY",
                "expired_at": "2026-08-15T12:00:00+03:00",
                "subscription_url": "https://example.test/subscription",
            },
        )
    )
    reissue_route = respx.post(f"{BASE}/api/v1/vpn/reissue/").mock(
        return_value=httpx.Response(202, json={"status": "PREPARING"})
    )

    status = await client.get_status(telegram_id=42)
    reissue = await client.reissue(telegram_id=42)

    assert status.status is VPNAccessStatus.READY
    assert status.subscription_url == "https://example.test/subscription"
    assert reissue is VPNAccessStatus.PREPARING
    assert reissue_route.calls.last.request.content == b"username=42"
