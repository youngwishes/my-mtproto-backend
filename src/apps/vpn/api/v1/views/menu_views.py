from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.permissions import BotAuthToken
from apps.users.selectors import get_user_by_username
from apps.vpn.api.v1.serializers import VPNMenuSerializer
from apps.vpn.selectors import get_vpn_subscription_by_user_id


class VPNMenuView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["get"]

    def get(self, request: Request) -> Response:
        serializer = VPNMenuSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        user = get_user_by_username(username=serializer.validated_data["username"])
        if user is None:
            return self._none_response()

        subscription = get_vpn_subscription_by_user_id(user_id=user.pk)
        if subscription is None:
            return self._none_response()

        return Response(
            {
                "status": (
                    "active"
                    if subscription.is_active and subscription.expired_at > timezone.now()
                    else "expired"
                ),
                "expired_at": subscription.expired_at,
                "subscription_url": (
                    f"{settings.VPN_SUBSCRIPTION_BASE_URL.rstrip('/')}"
                    f"/api/v1/vpn/subscriptions/{subscription.token}/"
                ),
            },
        )

    @staticmethod
    def _none_response() -> Response:
        return Response(
            {"status": "none", "expired_at": None, "subscription_url": None},
        )
