import json
import logging
from json import JSONDecodeError
from re import compile

logger = logging.getLogger(__name__)

_VPN_SUBSCRIPTION_PATH = compile(r"^/api/v1/vpn/subscriptions/[^/]+/$")
_REDACTED_VPN_SUBSCRIPTION_PATH = "/api/v1/vpn/subscriptions/[REDACTED]/"


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin"):
            return self.get_response(request)

        if request.method in ["POST", "PUT", "PATCH"] and request.body:
            try:
                body = json.loads(request.body)
            except JSONDecodeError:
                body = request.body.decode("utf-8")
            logger.info(
                {
                    "method": request.method,
                    "path": request.path,
                    "headers": dict(request.headers),
                    "body": body,
                }
            )

        response = self.get_response(request)

        if _VPN_SUBSCRIPTION_PATH.fullmatch(request.path):
            request.path = _REDACTED_VPN_SUBSCRIPTION_PATH

        return response
