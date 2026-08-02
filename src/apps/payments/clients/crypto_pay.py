from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import final

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.payments.exceptions import CryptoPayClientError
from apps.payments.services.dtos import CryptoInvoiceDTO


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CryptoPayClient:
    """Thin HTTP boundary for the Crypto Pay invoice API."""

    base_url: str
    api_token: str
    timeout: float

    def create_invoice(
        self,
        *,
        amount: Decimal,
        payload: str,
        description: str,
    ) -> CryptoInvoiceDTO:
        result = self._request_json(
            method="POST",
            endpoint="createInvoice",
            data={
                "currency_type": "fiat",
                "fiat": "RUB",
                "amount": format(amount, ".2f"),
                "accepted_assets": "USDT,TON",
                "expires_in": 1800,
                "payload": payload,
                "description": description,
            },
        )
        return self._to_invoice(item=result)

    def get_invoices(self, *, invoice_ids: list[int]) -> list[CryptoInvoiceDTO]:
        result = self._request_json(
            method="GET",
            endpoint="getInvoices",
            data={"invoice_ids": ",".join(map(str, invoice_ids))},
        )
        items = result.get("items")
        if not isinstance(items, list):
            raise CryptoPayClientError("cryptopay_malformed")
        return [self._to_invoice(item=item) for item in items]

    def _request_json(
        self,
        *,
        method: str,
        endpoint: str,
        data: dict[str, str | int],
    ) -> dict[str, object]:
        try:
            request_kwargs = {
                "headers": {"Crypto-Pay-API-Token": self.api_token},
                "timeout": self.timeout,
            }
            if method == "GET":
                response = requests.get(
                    f"{self.base_url.rstrip('/')}/api/{endpoint}",
                    params=data,
                    **request_kwargs,
                )
            else:
                response = requests.post(
                    f"{self.base_url.rstrip('/')}/api/{endpoint}",
                    data=data,
                    **request_kwargs,
                )
            response.raise_for_status()
            envelope = response.json()
        except requests.Timeout as exc:
            raise CryptoPayClientError("cryptopay_timeout") from exc
        except (requests.RequestException, ValueError) as exc:
            raise CryptoPayClientError("cryptopay_unavailable") from exc
        if not isinstance(envelope, dict):
            raise CryptoPayClientError("cryptopay_malformed")
        if envelope.get("ok") is not True:
            raise CryptoPayClientError("cryptopay_rejected")
        result = envelope.get("result")
        if not isinstance(result, dict):
            raise CryptoPayClientError("cryptopay_malformed")
        return result

    def _to_invoice(self, *, item: object) -> CryptoInvoiceDTO:
        try:
            if not isinstance(item, dict):
                raise TypeError
            invoice_id = item["invoice_id"]
            status = item["status"]
            currency_type = item["currency_type"]
            fiat = item["fiat"]
            amount = Decimal(str(item["amount"]))
            accepted_assets = item["accepted_assets"]
            paid_asset = item.get("paid_asset")
            payload = item["payload"]
            bot_invoice_url = item["bot_invoice_url"]
            created_at = _parse_provider_datetime(value=item["created_at"])
            expiration_date = _parse_provider_datetime(value=item["expiration_date"])
            paid_at = _parse_provider_datetime(
                value=item.get("paid_at"),
                allow_none=True,
            )
            if (
                not isinstance(invoice_id, int)
                or isinstance(invoice_id, bool)
                or not isinstance(status, str)
                or not isinstance(currency_type, str)
                or not isinstance(fiat, str | None)
                or not isinstance(accepted_assets, str)
                or not isinstance(paid_asset, str | None)
                or not isinstance(payload, str)
                or not isinstance(bot_invoice_url, str)
            ):
                raise TypeError
            return CryptoInvoiceDTO(
                invoice_id=invoice_id,
                status=status,
                currency_type=currency_type,
                fiat=fiat,
                amount=amount,
                accepted_assets=frozenset(accepted_assets.split(",")),
                paid_asset=paid_asset,
                payload=payload,
                bot_invoice_url=bot_invoice_url,
                created_at=created_at,
                expiration_date=expiration_date,
                paid_at=paid_at,
            )
        except (CryptoPayClientError, InvalidOperation, KeyError, TypeError, ValueError) as exc:
            raise CryptoPayClientError("cryptopay_malformed") from exc


def _parse_provider_datetime(*, value: object, allow_none: bool = False) -> datetime | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str):
        raise CryptoPayClientError("cryptopay_malformed")
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CryptoPayClientError("cryptopay_malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CryptoPayClientError("cryptopay_malformed")
    return parsed


def get_crypto_pay_client() -> CryptoPayClient:
    """Build a configured Crypto Pay client without exposing its token."""
    if not settings.CRYPTOPAY_API_TOKEN:
        raise ImproperlyConfigured("CRYPTOPAY_API_TOKEN is required")
    if settings.CRYPTOPAY_REQUEST_TIMEOUT <= 0:
        raise ImproperlyConfigured("CRYPTOPAY_REQUEST_TIMEOUT must be positive")
    return CryptoPayClient(
        base_url=settings.CRYPTOPAY_BASE_URL,
        api_token=settings.CRYPTOPAY_API_TOKEN,
        timeout=settings.CRYPTOPAY_REQUEST_TIMEOUT,
    )
