from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin"):
            return self.get_response(request)

        if request.method in ["POST", "PUT", "PATCH"] and request.body:
            logger.info(
                {
                    "method": request.method,
                    "path": request.path,
                    "headers": "[redacted]",
                    "body": "[redacted]",
                }
            )

        response = self.get_response(request)

        return response
