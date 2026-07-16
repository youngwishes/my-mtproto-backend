from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import final
from urllib.parse import parse_qsl, unquote, urlsplit
from uuid import UUID


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ValidatedVPNLink:
    uuid: UUID
    host: str
    port: int
    location: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ValidateVPNSubscriptionService:
    """Strict parser representing the supported MVP client import profile."""

    def __call__(self, *, payload: bytes) -> tuple[ValidatedVPNLink, ...]:
        try:
            plaintext = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("invalid subscription base64") from exc
        if base64.b64encode(plaintext) != payload:
            raise ValueError("noncanonical subscription base64")
        if not plaintext:
            return ()
        try:
            decoded = plaintext.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("subscription is not UTF-8") from exc
        if decoded.endswith("\n") or "\r" in decoded:
            raise ValueError("invalid subscription newline framing")
        return tuple(self._parse_link(value=line) for line in decoded.split("\n"))

    def _parse_link(self, *, value: str) -> ValidatedVPNLink:
        parsed = urlsplit(value)
        if parsed.scheme != "vless" or parsed.password is not None:
            raise ValueError("unsupported subscription scheme")
        try:
            credential = UUID(parsed.username or "")
            host = parsed.hostname or ""
            port = parsed.port
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid VLESS authority") from exc
        if not host or port is None or not parsed.fragment:
            raise ValueError("incomplete VLESS link")
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        expected_keys = ("encryption", "flow", "security", "sni", "fp", "pbk", "sid", "type")
        if tuple(key for key, _ in pairs) != expected_keys:
            raise ValueError("unsupported VLESS query shape")
        query = dict(pairs)
        expected_values = {
            "encryption": "none",
            "flow": "xtls-rprx-vision",
            "security": "reality",
            "fp": "chrome",
            "type": "tcp",
        }
        if any(query[key] != value for key, value in expected_values.items()):
            raise ValueError("unsupported VLESS profile")
        if not all(query[key] for key in ("sni", "pbk", "sid")):
            raise ValueError("missing REALITY client parameter")
        return ValidatedVPNLink(
            uuid=credential,
            host=host,
            port=port,
            location=unquote(parsed.fragment),
        )
