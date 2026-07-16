from __future__ import annotations

import base64
from collections.abc import Iterable
from dataclasses import dataclass
from ipaddress import IPv6Address
from typing import Protocol, final
from urllib.parse import quote, urlencode
from uuid import UUID


class VPNSubscriptionNode(Protocol):
    number: int
    location: str
    host: str
    port: int
    reality_public_key: str
    reality_short_id: str
    reality_server_name: str
    reality_fingerprint: str
    reality_flow: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class BuildVPNSubscriptionService:
    """Build a Base64 plaintext subscription from public node parameters only."""

    def __call__(
        self, *, published_uuid: UUID, nodes: Iterable[VPNSubscriptionNode]
    ) -> bytes:
        links = tuple(
            self._build_link(published_uuid=published_uuid, node=node)
            for node in sorted(nodes, key=lambda item: item.number)
        )
        return base64.b64encode("\n".join(links).encode("utf-8"))

    def _build_link(self, *, published_uuid: UUID, node: VPNSubscriptionNode) -> str:
        authority_host = self._authority_host(host=node.host)
        query = urlencode(
            (
                ("encryption", "none"),
                ("flow", node.reality_flow),
                ("security", "reality"),
                ("sni", node.reality_server_name),
                ("fp", node.reality_fingerprint),
                ("pbk", node.reality_public_key),
                ("sid", node.reality_short_id),
                ("type", "tcp"),
            ),
            quote_via=quote,
        )
        fragment = quote(node.location, safe="")
        return (
            f"vless://{published_uuid}@{authority_host}:{node.port}?{query}#{fragment}"
        )

    @staticmethod
    def _authority_host(*, host: str) -> str:
        try:
            IPv6Address(host)
        except ValueError:
            return host
        return f"[{host}]"


def get_build_vpn_subscription_service() -> BuildVPNSubscriptionService:
    return BuildVPNSubscriptionService()
