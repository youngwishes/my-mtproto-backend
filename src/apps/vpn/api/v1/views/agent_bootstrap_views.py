from __future__ import annotations

from secrets import compare_digest

from django.conf import settings
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.vpn.api.v1.serializers import AgentProfileSerializer
from apps.vpn.selectors import get_active_vpn_subscriptions


class VPNAgentTokenPermission(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return compare_digest(
            request.headers.get("Authorization", ""),
            f"Bearer {settings.VPN_AGENT_TOKEN}",
        )


class AgentBootstrapProfilesView(APIView):
    permission_classes = (VPNAgentTokenPermission,)
    http_method_names = ["get"]

    def get(self, request: Request) -> Response:
        profiles = [
            {
                "access_id": subscription.pk,
                "vless_uuid": subscription.vless_uuid,
                "hysteria_secret": subscription.hysteria_secret,
            }
            for subscription in get_active_vpn_subscriptions()
        ]
        return Response(AgentProfileSerializer(profiles, many=True).data)
