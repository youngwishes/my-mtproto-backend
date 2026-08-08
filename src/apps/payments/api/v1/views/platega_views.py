from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.api.v1.serializers import (
    CreatePlategaInvoiceRequestSerializer,
    CreatePlategaInvoiceResponseSerializer,
)
from apps.payments.exceptions import (
    PlategaInvoiceCreationInProgress,
    PlategaInvoiceUnavailable,
)
from apps.payments.services import get_create_or_reuse_platega_invoice_service
from apps.payments.services.dtos import CreatePlategaInvoiceIn
from apps.users.permissions import BotAuthToken


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


def _safe_error_response(
    *,
    exc: PlategaInvoiceCreationInProgress | PlategaInvoiceUnavailable,
    response_status: int,
) -> Response:
    return Response(
        data={"error": exc.message, "detail": dict(exc.context)},
        status=response_status,
    )
