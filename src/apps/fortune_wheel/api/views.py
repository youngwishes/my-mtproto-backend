from __future__ import annotations

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.fortune_wheel.api.serializers import (
    FortuneWheelCooldownResponseSerializer,
    FortuneWheelSpinResponseSerializer,
    FortuneWheelStatusResponseSerializer,
)
from apps.fortune_wheel.authentication import (
    TelegramMiniAppAuthentication,
    TelegramMiniAppPrincipal,
)
from apps.fortune_wheel.exceptions import (
    FortuneWheelCooldown,
    FortuneWheelRegistrationRequired,
    FortuneWheelRetryable,
)
from apps.fortune_wheel.services import (
    get_fortune_wheel_status_service,
    get_spin_fortune_wheel_service,
)


class FortuneWheelAPIView(APIView):
    authentication_classes = (TelegramMiniAppAuthentication,)
    permission_classes = (IsAuthenticated,)
    http_method_names = ["post"]

    @staticmethod
    def telegram_id(request: Request) -> str:
        principal = request.user
        assert isinstance(principal, TelegramMiniAppPrincipal)
        return principal.telegram_id


class FortuneWheelStatusView(FortuneWheelAPIView):
    def post(self, request: Request) -> Response:
        try:
            result = get_fortune_wheel_status_service()(
                telegram_id=self.telegram_id(request)
            )
        except FortuneWheelRetryable as exc:
            return Response(
                {"error": exc.message},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        outgoing = FortuneWheelStatusResponseSerializer(
            instance={
                **result.asdict(),
                "registration_url": None if result.registered else settings.BOT_LINK,
            }
        )
        return Response(outgoing.data, status=status.HTTP_200_OK)


class FortuneWheelSpinView(FortuneWheelAPIView):
    def post(self, request: Request) -> Response:
        telegram_id = self.telegram_id(request)
        try:
            result = get_spin_fortune_wheel_service()(telegram_id=telegram_id)
        except FortuneWheelRegistrationRequired as exc:
            return Response(
                {"error": exc.message, "registration_url": settings.BOT_LINK},
                status=status.HTTP_403_FORBIDDEN,
            )
        except FortuneWheelCooldown as exc:
            outgoing = FortuneWheelCooldownResponseSerializer(
                instance={"error": exc.message, **exc.context}
            )
            return Response(outgoing.data, status=status.HTTP_409_CONFLICT)
        except FortuneWheelRetryable as exc:
            return Response(
                {"error": exc.message},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        outgoing = FortuneWheelSpinResponseSerializer(instance=result)
        return Response(outgoing.data, status=status.HTTP_200_OK)
