from __future__ import annotations

import hashlib
from unittest import TestCase

from redis.exceptions import ConnectionError as RedisConnectionError

from apps.vpn.infra.subscription_throttle import RedisVPNSubscriptionThrottle


class FakeRedis:
    def __init__(self, *, fail: bool = False, fail_after: bool = False) -> None:
        self.values: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.keys: list[str] = []
        self.fail = fail
        self.fail_after = fail_after
        self.script = ""

    def eval(self, script: str, key_count: int, key: str, window: int):
        if self.fail:
            raise RedisConnectionError("unavailable")
        self.script = script
        self.keys.append(key)
        self.values[key] = self.values.get(key, 0) + 1
        if self.values[key] == 1:
            self.ttls[key] = int(window)
        if self.ttls.get(key, -1) < 0:
            self.ttls[key] = int(window)
        if self.fail_after:
            raise RedisConnectionError("reply lost")
        return [self.values[key], self.ttls[key]]


class RedisVPNSubscriptionThrottleTest(TestCase):
    def _throttle(self, client: FakeRedis, *, limit: int = 1):
        return RedisVPNSubscriptionThrottle(
            client=client,
            limit=limit,
            window_seconds=60,
            trusted_proxy_networks=("10.0.0.0/8", "2001:db8::/32"),
        )

    def test_atomic_script_hashes_token_and_sets_ttl_on_first_increment(self) -> None:
        client = FakeRedis()
        throttle = self._throttle(client)
        token = "secret-subscription-token"
        meta = {"REMOTE_ADDR": "203.0.113.8", "HTTP_X_FORWARDED_FOR": "1.1.1.1"}

        self.assertIsNone(throttle.allow(token=token, meta=meta))
        self.assertEqual(throttle.allow(token=token, meta=meta), 60)
        key = client.keys[0]
        self.assertNotIn(token, key)
        self.assertIn(hashlib.sha256(token.encode()).hexdigest(), key)
        self.assertIn(hashlib.sha256(b"203.0.113.8").hexdigest(), key)
        self.assertIn("INCR", client.script)
        self.assertIn("EXPIRE", client.script)
        self.assertEqual(client.ttls[key], 60)

    def test_parses_trusted_chain_right_to_left_for_ipv4_and_ipv6(self) -> None:
        cases = (
            ("10.0.0.2", "198.51.100.4, 10.1.1.1", "198.51.100.4"),
            ("2001:db8::2", "2001:4860::4, 2001:db8::1", "2001:4860::4"),
        )
        for peer, chain, expected in cases:
            with self.subTest(peer=peer):
                client = FakeRedis()
                self._throttle(client, limit=30).allow(
                    token="t", meta={"REMOTE_ADDR": peer, "HTTP_X_FORWARDED_FOR": chain}
                )
                self.assertIn(hashlib.sha256(expected.encode()).hexdigest(), client.keys[0])

    def test_untrusted_peer_cannot_spoof_and_malformed_chain_falls_back_to_peer(self) -> None:
        for peer, chain in (("203.0.113.8", "1.1.1.1"), ("10.0.0.2", "bad, 10.1.1.1")):
            client = FakeRedis()
            self._throttle(client, limit=30).allow(
                token="t", meta={"REMOTE_ADDR": peer, "HTTP_X_FORWARDED_FOR": chain}
            )
            self.assertIn(hashlib.sha256(peer.encode()).hexdigest(), client.keys[0])

    def test_redis_failure_is_raised_for_fail_closed_http_mapping(self) -> None:
        with self.assertRaises(RedisConnectionError):
            self._throttle(FakeRedis(fail=True)).allow(
                token="t", meta={"REMOTE_ADDR": "203.0.113.8"}
            )

    def test_atomic_operation_repairs_eternal_key_and_reply_loss_keeps_ttl(self) -> None:
        client = FakeRedis()
        throttle = self._throttle(client, limit=30)
        token = "t"
        meta = {"REMOTE_ADDR": "203.0.113.8"}
        key = (
            "vpn:subscription:"
            + hashlib.sha256(token.encode()).hexdigest()
            + ":"
            + hashlib.sha256(b"203.0.113.8").hexdigest()
        )
        client.values[key] = 4
        self.assertIsNone(throttle.allow(token=token, meta=meta))
        self.assertEqual(client.ttls[key], 60)

        lost_reply = FakeRedis(fail_after=True)
        with self.assertRaises(RedisConnectionError):
            self._throttle(lost_reply).allow(token=token, meta=meta)
        self.assertEqual(next(iter(lost_reply.ttls.values())), 60)
