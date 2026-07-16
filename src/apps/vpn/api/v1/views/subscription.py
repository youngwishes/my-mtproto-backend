from __future__ import annotations

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView
from redis.exceptions import RedisError

from apps.vpn.api.v1.serializers import VPNSubscriptionTokenSerializer
from apps.vpn.enums import VPNAccessState
from apps.vpn.infra.subscription_throttle import get_subscription_throttle
from apps.vpn.selectors import (
    get_subscription_nodes,
    get_vpn_access_by_subscription_token,
)
from apps.vpn.services.build_subscription import get_build_vpn_subscription_service


class VPNSubscriptionView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request: Request, token: str) -> HttpResponse:
        serializer = VPNSubscriptionTokenSerializer(data={"token": token})
        if not serializer.is_valid():
            return self._response(body=b"", status=404)
        try:
            retry_after = get_subscription_throttle().allow(
                token=serializer.validated_data["token"], meta=request.META
            )
        except RedisError:
            return self._response(body=b"", status=503, retry_after=30)
        if retry_after is not None:
            return self._response(body=b"", status=429, retry_after=retry_after)
        access = get_vpn_access_by_subscription_token(token=token)
        if access is None:
            return self._response(body=b"", status=404)
        if (
            access.expired_at <= timezone.now()
            or access.disabled_at is not None
            or access.state in (VPNAccessState.EXPIRED, VPNAccessState.DISABLED_REFUND)
        ):
            return self._response(body=b"", status=200)
        if access.published_uuid is None:
            return self._response(body=b"", status=503, retry_after=30)
        body = get_build_vpn_subscription_service()(
            published_uuid=access.published_uuid,
            nodes=get_subscription_nodes(access=access),
        )
        return self._response(body=body, status=200)

    @staticmethod
    def _response(*, body: bytes, status: int, retry_after: int | None = None) -> HttpResponse:
        response = HttpResponse(body, status=status, content_type="text/plain; charset=utf-8")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        if retry_after is not None:
            response["Retry-After"] = str(retry_after)
        return response
