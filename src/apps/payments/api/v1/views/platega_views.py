from __future__ import annotations

import codecs
import logging
import secrets
from dataclasses import asdict
from decimal import Decimal, DecimalException
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import DatabaseError
from rest_framework import status
from rest_framework.exceptions import ParseError, UnsupportedMediaType
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils import json
from rest_framework.views import APIView

from apps.payments.api.v1.serializers import (
    CreatePlategaInvoiceRequestSerializer,
    CreatePlategaInvoiceResponseSerializer,
    PlategaCallbackSerializer,
)
from apps.payments.exceptions import (
    PlategaInvoiceCreationInProgress,
    PlategaInvoiceUnavailable,
    PlategaPaymentRetryable,
)
from apps.payments.services import (
    get_apply_platega_payment_service,
    get_create_or_reuse_platega_invoice_service,
    get_validate_platega_callback_service,
)
from apps.payments.services.dtos import CreatePlategaInvoiceIn, PlategaCallbackDTO
from apps.users.permissions import BotAuthToken

if TYPE_CHECKING:
    from typing import IO


logger = logging.getLogger(__name__)


class _DecimalJSONParser(JSONParser):
    def parse(
        self,
        stream: IO[bytes],
        media_type: str | None = None,
        parser_context: dict[str, object] | None = None,
    ) -> object:
        parser_context = parser_context or {}
        encoding = parser_context.get("encoding") or settings.DEFAULT_CHARSET

        try:
            decoded_stream = codecs.getreader(str(encoding))(stream)
            return json.load(
                decoded_stream,
                parse_int=Decimal,
                parse_float=Decimal,
                parse_constant=json.strict_constant,
            )
        except (ValueError, DecimalException) as exc:
            raise ParseError(f"JSON parse error - {exc}") from exc


class CreatePlategaInvoiceView(APIView):
    """Create or reuse one Platega SBP invoice for the bot."""

    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        incoming = CreatePlategaInvoiceRequestSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        try:
            result = get_create_or_reuse_platega_invoice_service()(
                request=CreatePlategaInvoiceIn(**incoming.validated_data),
            )
        except PlategaInvoiceCreationInProgress as exc:
            return _safe_error_response(
                exc=exc,
                response_status=status.HTTP_409_CONFLICT,
            )
        except PlategaInvoiceUnavailable as exc:
            return _safe_error_response(
                exc=exc,
                response_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        outgoing = CreatePlategaInvoiceResponseSerializer(instance=result)
        return Response(outgoing.data, status=status.HTTP_200_OK)


class PlategaCallbackView(APIView):
    """Authenticate Platega headers before parsing and applying a callback."""

    authentication_classes = ()
    permission_classes = ()
    parser_classes = (_DecimalJSONParser,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        configured_merchant = getattr(settings, "PLATEGA_MERCHANT_ID", "")
        configured_secret = getattr(settings, "PLATEGA_SECRET", "")
        supplied_merchant = request.META.get("HTTP_X_MERCHANTID", "")
        supplied_secret = request.META.get("HTTP_X_SECRET", "")

        merchant_matches = secrets.compare_digest(
            supplied_merchant.encode("utf-8"),
            configured_merchant.encode("utf-8"),
        )
        secret_matches = secrets.compare_digest(
            supplied_secret.encode("utf-8"),
            configured_secret.encode("utf-8"),
        )
        credentials_configured = bool(
            configured_merchant.strip() and configured_secret.strip()
        )
        if not credentials_configured or not (
            merchant_matches and secret_matches
        ):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            callback_data = request.data
        except (ParseError, UnsupportedMediaType):
            return Response(status=status.HTTP_200_OK)
        incoming = PlategaCallbackSerializer(data=callback_data)
        if not incoming.is_valid():
            return Response(status=status.HTTP_200_OK)

        try:
            validated = get_validate_platega_callback_service()(
                callback=PlategaCallbackDTO(**incoming.validated_data),
            )
        except DatabaseError:
            return Response(status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if validated.warning is not None:
            logger.warning(asdict(validated.warning))
        if validated.payment is None:
            return Response(status=status.HTTP_200_OK)

        try:
            get_apply_platega_payment_service()(payment=validated.payment)
        except (PlategaPaymentRetryable, DatabaseError):
            return Response(status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(status=status.HTTP_200_OK)


def _safe_error_response(
    *,
    exc: PlategaInvoiceCreationInProgress | PlategaInvoiceUnavailable,
    response_status: int,
) -> Response:
    return Response(
        data={"error": exc.message, "detail": dict(exc.context)},
        status=response_status,
    )
