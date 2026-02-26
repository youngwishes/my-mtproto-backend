import json
import logging
from json import JSONDecodeError

logger = logging.getLogger(__name__)


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

        return response
