from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.permissions import BotAuthToken
from apps.vpn.selectors import is_vpn_bot_enabled


class VPNBotSettingsView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["get"]

    def get(self, request: Request) -> Response:
        return Response({"enabled": is_vpn_bot_enabled()})
