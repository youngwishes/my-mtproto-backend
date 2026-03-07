from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.api.v1.serializers import CreatePaymentSerializer
from apps.payments.services.create_payment_service import get_create_payment_service
from apps.users.permissions import BotAuthToken


class CreatePaymentView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = get_create_payment_service()
        service(username=serializer.validated_data["username"])

        return Response(status=status.HTTP_200_OK)
