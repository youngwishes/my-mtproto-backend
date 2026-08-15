from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.permissions import BotAuthToken
from apps.vpn.api.v1.serializers import ReissueVPNSubscriptionSerializer
from apps.vpn.services import get_reissue_vpn_subscription_service


class ReissueVPNSubscriptionView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        serializer = ReissueVPNSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reissue = get_reissue_vpn_subscription_service()(
            username=serializer.validated_data["username"],
        )
        return Response(
            {"expired_at": reissue.expired_at, "subscription_url": reissue.subscription_url},
            status=status.HTTP_200_OK,
        )
