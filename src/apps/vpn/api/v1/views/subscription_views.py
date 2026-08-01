from __future__ import annotations

from django.http import Http404, HttpResponse
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.vpn.services import get_subscription_service


class VPNSubscriptionView(APIView):
    http_method_names = ["get"]

    def get(self, request: Request, token: str) -> HttpResponse:
        subscription = get_subscription_service()(token=token)
        if subscription is None:
            raise Http404

        response = HttpResponse(subscription, content_type="text/plain")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["profile-title"] = "mtprotokeys.ru"
        return response
