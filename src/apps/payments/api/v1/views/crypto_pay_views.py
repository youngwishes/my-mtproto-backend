from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.api.v1.serializers import (
    CreateCryptoInvoiceRequestSerializer,
    CreateCryptoInvoiceResponseSerializer,
)
from apps.payments.exceptions import (
    CryptoInvoiceCreationInProgress,
    CryptoInvoiceUnavailable,
)
from apps.payments.services import get_create_or_reuse_crypto_invoice_service
from apps.payments.services.dtos import CreateCryptoInvoiceIn
from apps.users.permissions import BotAuthToken


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
