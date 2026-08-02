from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from dataclasses import asdict
from json import JSONDecodeError

from django.conf import settings
from django.db import OperationalError
from django.http import Http404
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.api.v1.serializers import (
    CreateCryptoInvoiceRequestSerializer,
    CreateCryptoInvoiceResponseSerializer,
    CryptoWebhookSerializer,
)
from apps.payments.exceptions import (
    CryptoInvoiceCreationInProgress,
    CryptoInvoiceUnavailable,
    CryptoPaymentRetryable,
)
from apps.payments.services import (
    get_apply_crypto_payment_service,
    get_create_or_reuse_crypto_invoice_service,
    get_validate_crypto_invoice_service,
)
from apps.payments.services.dtos import (
    CreateCryptoInvoiceIn,
    CryptoInvoiceDTO,
    CryptoWebhookWarningDTO,
)
from apps.payments.tasks import warn_crypto_webhook_admin_task
from apps.users.permissions import BotAuthToken

logger = logging.getLogger(__name__)


def _safe_error_response(
    *,
    exc: CryptoInvoiceCreationInProgress | CryptoInvoiceUnavailable,
    response_status: int,
) -> Response:
    return Response(
        data={
            "error": exc.message,
            "detail": dict(exc.context),
        },
        status=response_status,
    )


class CreateCryptoInvoiceView(APIView):
    """Create or reuse one validated Crypto Pay invoice for the bot."""

    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        incoming = CreateCryptoInvoiceRequestSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        try:
            result = get_create_or_reuse_crypto_invoice_service()(
                request=CreateCryptoInvoiceIn(**incoming.validated_data),
            )
        except CryptoInvoiceCreationInProgress as exc:
            return _safe_error_response(
                exc=exc,
                response_status=status.HTTP_409_CONFLICT,
            )
        except CryptoInvoiceUnavailable as exc:
            return _safe_error_response(
                exc=exc,
                response_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        outgoing = CreateCryptoInvoiceResponseSerializer(instance=result)
        return Response(outgoing.data, status=status.HTTP_200_OK)


class CryptoPayWebhookView(APIView):
    """Authenticate raw Crypto Pay events before semantic validation or apply."""

    authentication_classes = ()
    permission_classes = ()
    http_method_names = ["post"]

    def post(self, request: Request, webhook_secret: str) -> Response:
        configured_secret = getattr(settings, "CRYPTOPAY_WEBHOOK_SECRET", "")
        if not configured_secret or not secrets.compare_digest(
            webhook_secret,
            configured_secret,
        ):
            raise Http404

        raw_body = request.body
        api_token = getattr(settings, "CRYPTOPAY_API_TOKEN", "")
        supplied_signature = request.headers.get("crypto-pay-api-signature", "")
        if not api_token or not supplied_signature:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        key = hashlib.sha256(api_token.encode()).digest()
        expected_signature = hmac.new(key, raw_body, hashlib.sha256).hexdigest()
        if not secrets.compare_digest(supplied_signature, expected_signature):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            parsed = json.loads(raw_body)
        except (UnicodeDecodeError, JSONDecodeError):
            return Response(status=status.HTTP_400_BAD_REQUEST)
        serializer = CryptoWebhookSerializer(data=parsed)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["update_type"] != "invoice_paid":
            return Response(status=status.HTTP_400_BAD_REQUEST)
        return self._handle_signed(serializer=serializer)

    @staticmethod
    def _handle_signed(*, serializer: CryptoWebhookSerializer) -> Response:
        data = serializer.validated_data
        invoice = CryptoInvoiceDTO(**data["payload"])
        try:
            validated = get_validate_crypto_invoice_service()(
                update_id=data["update_id"],
                invoice=invoice,
            )
        except OperationalError:
            return Response(status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if isinstance(validated, CryptoWebhookWarningDTO):
            warning = asdict(validated)
            logger.warning(warning)
            try:
                warn_crypto_webhook_admin_task.delay(warning)
            except Exception:
                return Response(status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return Response(status=status.HTTP_200_OK)

        try:
            get_apply_crypto_payment_service()(payment=validated)
        except (CryptoPaymentRetryable, OperationalError):
            return Response(status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(status=status.HTTP_200_OK)
