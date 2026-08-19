from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.api.v1.serializers import (
    ActivateGiftCertificateSerializer,
    CreateGiftCertificateResponseSerializer,
    CreateGiftCertificateSerializer,
)
from apps.payments.services import (
    get_activate_gift_certificate_service,
    get_create_gift_certificate_service,
)
from apps.payments.services.dtos import (
    ActivateGiftCertificateIn,
    CreateGiftCertificateIn,
    HistoricalPurchaseReplayDTO,
)
from apps.users.permissions import BotAuthToken


class CreateGiftCertificateView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        serializer = CreateGiftCertificateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = get_create_gift_certificate_service()(
            certificate=CreateGiftCertificateIn(**serializer.validated_data),
        )

        if isinstance(result, HistoricalPurchaseReplayDTO):
            return Response(data=result.asdict(), status=status.HTTP_200_OK)
        outgoing = CreateGiftCertificateResponseSerializer(instance=result)
        return Response(data=outgoing.data, status=status.HTTP_200_OK)


class ActivateGiftCertificateView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        serializer = ActivateGiftCertificateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = get_activate_gift_certificate_service()(
            activation=ActivateGiftCertificateIn(**serializer.validated_data),
        )

        return Response(
            data={"expired_date": result.expired_date},
            status=status.HTTP_200_OK,
        )
