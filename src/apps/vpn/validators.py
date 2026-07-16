from __future__ import annotations

import base64
import binascii
import ipaddress
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError

_DNS_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$", re.IGNORECASE)
_ENV_LOOKUP_KEY = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
_EVEN_HEX = re.compile(r"^(?:[0-9a-fA-F]{2}){1,8}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_X25519_PUBLIC_KEY = re.compile(r"^[A-Za-z0-9_-]{43}$")


def _is_dns_name(value: str) -> bool:
    candidate = value[:-1] if value.endswith(".") else value
    return bool(
        candidate
        and len(candidate) <= 253
        and "." in candidate
        and all(_DNS_LABEL.fullmatch(label) for label in candidate.split("."))
    )


def validate_public_host(value: str) -> None:
    """Accept an unbracketed IPv4/IPv6 address or a DNS hostname."""
    if any(character.isspace() for character in value) or "/" in value:
        raise ValidationError("Укажите DNS-имя, IPv4 или IPv6 без схемы и пути.")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        if not _is_dns_name(value):
            raise ValidationError("Укажите корректное DNS-имя, IPv4 или IPv6.")


def validate_sni(value: str) -> None:
    """Require a DNS hostname: REALITY SNI must not be an IP literal."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        if _is_dns_name(value):
            return
    raise ValidationError("SNI должен быть корректным DNS-именем.")


def validate_https_base_url(value: str) -> None:
    parsed = urlsplit(value)
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise ValidationError("Некорректный HTTPS URL агента.") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path
        or parsed_port is None and ":" in parsed.netloc.rsplit("]", 1)[-1]
    ):
        raise ValidationError("Agent base URL должен быть HTTPS origin без credentials и пути.")


def validate_agent_secret_lookup_key(value: str) -> None:
    if not _ENV_LOOKUP_KEY.fullmatch(value):
        raise ValidationError("Укажите имя секрета environment/Ansible, а не token.")


def validate_x25519_public_key(value: str) -> None:
    if not _X25519_PUBLIC_KEY.fullmatch(value):
        raise ValidationError("Некорректный X25519 public key.")
    try:
        decoded = base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
    except (ValueError, binascii.Error) as exc:
        raise ValidationError("Некорректный X25519 public key.") from exc
    canonical = base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")
    if len(decoded) != 32 or canonical != value:
        raise ValidationError("X25519 public key должен кодировать ровно 32 байта.")


def validate_reality_short_id(value: str) -> None:
    if not _EVEN_HEX.fullmatch(value):
        raise ValidationError("Short ID должен быть чётной hex-строкой длиной не более 16.")


def validate_optional_sha256(value: str) -> None:
    if value and not _SHA256.fullmatch(value):
        raise ValidationError("Snapshot hash должен быть SHA-256 в нижнем hex-регистре.")
