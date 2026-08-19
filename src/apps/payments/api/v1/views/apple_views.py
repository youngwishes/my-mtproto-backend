from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.api.v1.serializers import (
    AppleRedemptionConfirmRequestSerializer,
    AppleRedemptionConfirmResponseSerializer,
    AppleRedemptionPreviewRequestSerializer,
    AppleRedemptionPreviewResponseSerializer,
    AppleStatusRequestSerializer,
    AppleStatusResponseSerializer,
)
from apps.payments.exceptions import AppleRedemptionRetryable
from apps.payments.services import (
    get_apple_status_service,
    get_confirm_apple_redemption_service,
    get_preview_apple_redemption_service,
)
from apps.payments.services.dtos import (
    AppleRedemptionConfirmIn,
    AppleRedemptionPreviewIn,
    AppleStatusIn,
)
from apps.users.permissions import BotAuthToken


def _retryable_response(*, exc: AppleRedemptionRetryable) -> Response:
    return Response(
        data={"error": exc.message, "detail": dict(exc.context)},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


class AppleStatusView(APIView):
    """Return backend-authoritative apple balance and level status."""

    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        incoming = AppleStatusRequestSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        try:
            result = get_apple_status_service()(
                request=AppleStatusIn(**incoming.validated_data)
            )
        except AppleRedemptionRetryable as exc:
            return _retryable_response(exc=exc)
        outgoing = AppleStatusResponseSerializer(instance=result)
        return Response(data=outgoing.data, status=status.HTTP_200_OK)


class AppleRedemptionPreviewView(APIView):
    """Create an immutable quote for one-day or all-apples redemption."""

    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        incoming = AppleRedemptionPreviewRequestSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        try:
            result = get_preview_apple_redemption_service()(
                request=AppleRedemptionPreviewIn(**incoming.validated_data)
            )
        except AppleRedemptionRetryable as exc:
            return _retryable_response(exc=exc)
        outgoing = AppleRedemptionPreviewResponseSerializer(instance=result)
        return Response(data=outgoing.data, status=status.HTTP_200_OK)


class AppleRedemptionConfirmView(APIView):
    """Confirm one owner-scoped saved redemption quote."""

    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        incoming = AppleRedemptionConfirmRequestSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        try:
            result = get_confirm_apple_redemption_service()(
                request=AppleRedemptionConfirmIn(**incoming.validated_data)
            )
        except AppleRedemptionRetryable as exc:
            return _retryable_response(exc=exc)
        outgoing = AppleRedemptionConfirmResponseSerializer(instance=result)
        return Response(data=outgoing.data, status=status.HTTP_200_OK)
