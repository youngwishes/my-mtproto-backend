from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from math import isfinite
from typing import final
from urllib.parse import urlsplit
from uuid import UUID

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.payments.exceptions import PlategaClientError
from apps.payments.services.dtos import PlategaTransactionDTO


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class PlategaClient:
    """Thin POST-only HTTP boundary for Platega SBP transaction creation."""

    base_url: str
    merchant_id: str
    secret: str
    timeout: float

    def create_transaction(
        self,
        *,
        amount: Decimal,
        description: str,
        return_url: str,
        public_id: UUID,
        telegram_id: str,
        telegram_username: str,
    ) -> PlategaTransactionDTO:
        body = _serialize_create_transaction_body(
            amount=amount,
            description=description,
            return_url=return_url,
            public_id=public_id,
            telegram_id=telegram_id,
            telegram_username=telegram_username,
        )
        request_error: str | None = None
        response: requests.Response | None = None
        try:
            response = requests.post(
                f"{self.base_url.rstrip('/')}/transaction/process",
                data=body.encode(),
                headers={
                    "X-MerchantId": self.merchant_id,
                    "X-Secret": self.secret,
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        except requests.Timeout:
            request_error = "timeout"
        except requests.RequestException:
            request_error = "unavailable"

        if request_error is not None:
            raise PlategaClientError(request_error)
        assert response is not None
        if response.status_code != requests.codes.ok:
            raise PlategaClientError("unavailable")
        payload, response_error = _read_response_json(response=response)
        if response_error is not None:
            raise PlategaClientError(response_error)
        transaction, validation_error = self._to_transaction(
            payload=payload,
            return_url=return_url,
        )
        if validation_error is not None:
            raise PlategaClientError(validation_error)
        assert transaction is not None
        return transaction

    def _to_transaction(
        self,
        *,
        payload: object,
        return_url: str,
    ) -> tuple[PlategaTransactionDTO | None, str | None]:
        try:
            if not isinstance(payload, dict):
                raise TypeError
            transaction_id = UUID(payload["transactionId"])
            status = payload["status"]
            redirect_url = payload["redirect"]
            expires_in = _parse_expires_in(payload["expiresIn"])
            if expires_in is None:
                raise TypeError
            if not isinstance(status, str) or status != "PENDING":
                return None, "create_mismatch"
            if not isinstance(redirect_url, str) or not _is_usable_https_url(redirect_url):
                raise TypeError
            echo_error = _validate_optional_echoes(
                payload=payload,
                return_url=return_url,
                merchant_id=self.merchant_id,
            )
            if echo_error is not None:
                return None, echo_error
            return PlategaTransactionDTO(
                transaction_id=transaction_id,
                status=status,
                redirect_url=redirect_url,
                expires_in=expires_in,
            ), None
        except (AttributeError, KeyError, TypeError, ValueError):
            return None, "malformed"


def _serialize_create_transaction_body(
    *,
    amount: Decimal,
    description: str,
    return_url: str,
    public_id: UUID,
    telegram_id: str,
    telegram_username: str,
) -> str:
    username = telegram_username or telegram_id
    return "".join(
        (
            '{"paymentMethod":2,"paymentDetails":{"amount":',
            format(amount, ".2f"),
            ',"currency":"RUB"},"description":',
            json.dumps(description),
            ',"return":',
            json.dumps(return_url),
            ',"failedUrl":',
            json.dumps(return_url),
            ',"payload":',
            json.dumps(str(public_id)),
            ',"metadata":{"userId":',
            json.dumps(telegram_id),
            ',"userName":',
            json.dumps(username),
            "}}",
        )
    )


def _validate_optional_echoes(
    *,
    payload: dict[str, object],
    return_url: str,
    merchant_id: str,
) -> str | None:
    if "paymentMethod" in payload and payload["paymentMethod"] != "SBPQR":
        return "create_mismatch"
    if "return" in payload and payload["return"] != return_url:
        return "create_mismatch"
    if "merchantId" in payload and payload["merchantId"] != merchant_id:
        return "create_mismatch"
    return None


def _read_response_json(*, response: requests.Response) -> tuple[object | None, str | None]:
    try:
        return response.json(), None
    except ValueError:
        return None, "malformed"


def _parse_expires_in(value: object) -> timedelta | None:
    if value != "00:15:00":
        return None
    return timedelta(minutes=15)


def _is_usable_https_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and bool(hostname)
        and not any(character.isspace() for character in hostname)
        and (port is None or 1 <= port <= 65535)
    )


def get_platega_client() -> PlategaClient:
    """Build a configured Platega client without disclosing credentials."""
    if not settings.PLATEGA_MERCHANT_ID.strip():
        raise ImproperlyConfigured("PLATEGA_MERCHANT_ID is required")
    if not settings.PLATEGA_SECRET.strip():
        raise ImproperlyConfigured("PLATEGA_SECRET is required")
    if not _is_usable_https_url(settings.PLATEGA_BASE_URL):
        raise ImproperlyConfigured("PLATEGA_BASE_URL must be an HTTPS URL")
    if (
        not isinstance(settings.PLATEGA_REQUEST_TIMEOUT, int | float)
        or isinstance(settings.PLATEGA_REQUEST_TIMEOUT, bool)
        or not isfinite(settings.PLATEGA_REQUEST_TIMEOUT)
        or settings.PLATEGA_REQUEST_TIMEOUT <= 0
    ):
        raise ImproperlyConfigured("PLATEGA_REQUEST_TIMEOUT must be positive")
    return PlategaClient(
        base_url=settings.PLATEGA_BASE_URL,
        merchant_id=settings.PLATEGA_MERCHANT_ID,
        secret=settings.PLATEGA_SECRET,
        timeout=settings.PLATEGA_REQUEST_TIMEOUT,
    )
