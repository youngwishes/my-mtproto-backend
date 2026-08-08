import logging
from re import compile

logger = logging.getLogger(__name__)

_VPN_SUBSCRIPTION_PATH = compile(r"^/api/v1/vpn/subscriptions/[^/]+/$")
_REDACTED_VPN_SUBSCRIPTION_PATH = "/api/v1/vpn/subscriptions/[REDACTED]/"
_CRYPTO_WEBHOOK_PATH = compile(r"^/api/v1/payments/crypto/webhooks/[^/]+/$")
_REDACTED_CRYPTO_WEBHOOK_PATH = "/api/v1/payments/crypto/webhooks/[REDACTED]/"
_PLATEGA_CALLBACK_PATH = "/api/v1/payments/platega/callback/"


def _safe_request_log(request) -> dict[str, object]:
    if _CRYPTO_WEBHOOK_PATH.fullmatch(request.path):
        return {
            "method": request.method,
            "path": _REDACTED_CRYPTO_WEBHOOK_PATH,
        }
    return {
        "method": request.method,
        "path": request.path,
    }


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == _PLATEGA_CALLBACK_PATH:
            return self.get_response(request)

        if request.path.startswith("/admin"):
            return self.get_response(request)

        if request.method in ["POST", "PUT", "PATCH"] and request.body:
            logger.info(_safe_request_log(request))

        response = self.get_response(request)

        if _CRYPTO_WEBHOOK_PATH.fullmatch(request.path):
            request.path = _REDACTED_CRYPTO_WEBHOOK_PATH
        elif _VPN_SUBSCRIPTION_PATH.fullmatch(request.path):
            request.path = _REDACTED_VPN_SUBSCRIPTION_PATH

        return response
