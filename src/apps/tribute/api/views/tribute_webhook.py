from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.bot import notify_bad_request
from apps.tribute.api.serializers import TributeDigitalPaymentSerializer
from apps.tribute.permissions import IsTributeSign
from apps.tribute.services import get_tribute_digital_payment_service
from apps.tribute.services.dtos import NewDigitalPaymentDTO


class TributeWebhookView(APIView):
    permission_classes = (IsTributeSign,)

    @notify_bad_request
    def post(self, request: Request) -> Response:
        serializer = TributeDigitalPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = get_tribute_digital_payment_service()
        service(
            new_digital_payment=NewDigitalPaymentDTO(
                name=serializer.validated_data.get("name"),
                product_id=serializer.validated_data.get("payload").get("product_id"),
                product_name=serializer.validated_data.get("payload").get(
                    "product_name"
                ),
                amount=serializer.validated_data.get("payload").get("amount"),
                currency=serializer.validated_data.get("payload").get("currency"),
                telegram_user_id=serializer.validated_data.get("payload").get(
                    "telegram_user_id"
                ),
                purchase_created_at=serializer.validated_data.get("payload").get(
                    "purchase_created_at"
                ),
            )
        )
        return Response(status=status.HTTP_200_OK)
