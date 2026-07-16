from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
import redis


def get_vpn_alert_dedupe() -> Callable[..., bool]:
    client = redis.Redis.from_url(settings.CELERY_BROKER_URL)

    def claim(*, key: str, ttl_seconds: int) -> bool:
        try:
            return bool(client.set(key, "1", ex=ttl_seconds, nx=True))
        except Exception:
            return False

    return claim


__all__ = ["get_vpn_alert_dedupe"]
