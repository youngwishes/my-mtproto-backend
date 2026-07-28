from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.api.v1.serializers import (
    AcceptLegalConsentSerializer,
    LegalConsentStatusSerializer,
)
from apps.users.permissions import BotAuthToken
from apps.users.services import (
    get_accept_legal_consent_service,
    get_legal_consent_status_service,
)
from apps.users.services.dtos import AcceptLegalConsentIn, LegalConsentStatusIn


class LegalConsentStatusView(APIView):
    permission_classes = (BotAuthToken,)

    def post(self, request: Request) -> Response:
        serializer = LegalConsentStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = get_legal_consent_status_service()(
            data=LegalConsentStatusIn(**serializer.validated_data)
        )
        return Response(data=result.asdict(), status=status.HTTP_200_OK)


class AcceptLegalConsentView(APIView):
    permission_classes = (BotAuthToken,)

    def post(self, request: Request) -> Response:
        serializer = AcceptLegalConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = get_accept_legal_consent_service()(
            data=AcceptLegalConsentIn(**serializer.validated_data)
        )
        return Response(data=result.asdict(), status=status.HTTP_200_OK)
