from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.permissions import BotAuthToken
from apps.vpn.api.v1.serializers import FulfillVPNPaymentSerializer
from apps.vpn.services import get_fulfill_vpn_purchase_service
from apps.vpn.services.dtos import FulfillVPNPaymentIn


class FulfillVPNPaymentView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        serializer = FulfillVPNPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        purchase = get_fulfill_vpn_purchase_service()(
            payment=FulfillVPNPaymentIn(**serializer.validated_data),
        )
        return Response(
            {"expired_at": purchase.expired_at, "subscription_url": purchase.subscription_url},
            status=status.HTTP_200_OK,
        )
