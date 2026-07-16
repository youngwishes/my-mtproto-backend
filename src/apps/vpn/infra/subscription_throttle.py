from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from typing import Protocol, final

from django.conf import settings
from redis import Redis


class RedisCounter(Protocol):
    def eval(self, script: str, key_count: int, *args: object) -> object: ...


_ATOMIC_RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
if ttl < 0 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
  ttl = tonumber(ARGV[1])
end
return {count, ttl}
"""


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class RedisVPNSubscriptionThrottle:
    client: RedisCounter
    limit: int
    window_seconds: int
    trusted_proxy_networks: tuple[str, ...]

    def allow(self, *, token: str, meta: Mapping[str, str]) -> int | None:
        source_ip = self._source_ip(meta=meta)
        token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        ip_digest = hashlib.sha256(source_ip.encode("ascii")).hexdigest()
        key = f"vpn:subscription:{token_digest}:{ip_digest}"
        result = self.client.eval(
            _ATOMIC_RATE_LIMIT_SCRIPT, 1, key, self.window_seconds
        )
        count, ttl = (int(item) for item in result)  # type: ignore[union-attr]
        if count <= self.limit:
            return None
        return ttl if ttl > 0 else self.window_seconds

    def _source_ip(self, *, meta: Mapping[str, str]) -> str:
        peer = self._valid_ip(meta.get("REMOTE_ADDR", ""))
        if not self._is_trusted(value=peer):
            return peer
        forwarded = meta.get("HTTP_X_FORWARDED_FOR", "")
        if not forwarded:
            return peer
        try:
            chain = tuple(str(ip_address(value.strip())) for value in forwarded.split(","))
        except ValueError:
            return peer
        for candidate in reversed(chain):
            if not self._is_trusted(value=candidate):
                return candidate
        return peer

    def _is_trusted(self, *, value: str) -> bool:
        address = ip_address(value)
        return any(
            address in ip_network(network, strict=False)
            for network in self.trusted_proxy_networks
        )

    @staticmethod
    def _valid_ip(value: str) -> str:
        try:
            return str(ip_address(value))
        except ValueError:
            return "0.0.0.0"


def get_subscription_throttle() -> RedisVPNSubscriptionThrottle:
    client = Redis.from_url(settings.VPN_SUBSCRIPTION_REDIS_URL, decode_responses=True)
    return RedisVPNSubscriptionThrottle(
        client=client,
        limit=settings.VPN_SUBSCRIPTION_RATE_LIMIT,
        window_seconds=settings.VPN_SUBSCRIPTION_RATE_WINDOW_SECONDS,
        trusted_proxy_networks=tuple(settings.VPN_SUBSCRIPTION_TRUSTED_PROXY_NETWORKS),
    )
