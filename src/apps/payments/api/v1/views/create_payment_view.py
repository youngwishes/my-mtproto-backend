from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.api.v1.serializers import (
    CreatePaymentResponseSerializer,
    CreatePaymentSerializer,
)
from apps.payments.services import get_create_payment_service
from apps.payments.services.dtos import CreatePaymentIn, HistoricalPurchaseReplayDTO
from apps.users.permissions import BotAuthToken


class CreatePaymentView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = get_create_payment_service()(
            payment=CreatePaymentIn(**serializer.validated_data)
        )
        if isinstance(result, HistoricalPurchaseReplayDTO):
            return Response(data=result.asdict(), status=status.HTTP_200_OK)

        outgoing = CreatePaymentResponseSerializer(instance=result)
        return Response(data=outgoing.data, status=status.HTTP_200_OK)
