from __future__ import annotations

import logging
import time

from apps.vpn.observability import VPNMetric, emit_vpn_metric

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

        subscription_request = request.path.startswith("/api/v1/vpn/subscriptions/")
        started_at = time.monotonic() if subscription_request else 0.0
        response = self.get_response(request)

        if subscription_request:
            latency_ms = max(0, int((time.monotonic() - started_at) * 1000))
            logger.info(
                {
                    "event": "vpn_subscription_request",
                    "route": "/api/v1/vpn/subscriptions/:token/",
                    "status": response.status_code,
                    "latency_ms": latency_ms,
                    "rate_limited": int(response.status_code == 429),
                }
            )
            for metric in (
                VPNMetric(name="vpn_subscription_requests_total", value=1),
                VPNMetric(
                    name="vpn_subscription_latency_observed_ms", value=latency_ms
                ),
                VPNMetric(
                    name="vpn_subscription_rate_limited_total",
                    value=int(response.status_code == 429),
                ),
            ):
                try:
                    emit_vpn_metric(metric)
                except Exception:
                    pass

        return response
