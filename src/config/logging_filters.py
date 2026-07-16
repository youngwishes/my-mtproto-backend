from __future__ import annotations

import copy
import logging
import re
from typing import Any

from django.http import QueryDict


_SUBSCRIPTION_PATH = re.compile(r"/api/v1/vpn/subscriptions/[^/?\s]+/?")
_SAFE_PATH = "/api/v1/vpn/subscriptions/:token/"
_SUBSCRIPTION_QUERY = re.compile(r"(/api/v1/vpn/subscriptions/:token/)\?[^\s'\"]*")
_VLESS_URI = re.compile(r"vless://[^\s'\"]+", re.IGNORECASE)
_UUID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_AUTHORIZATION = re.compile(
    r"\bauthorization\s*[:=]\s*(?:bearer\s+)?[^\s,;]+",
    re.IGNORECASE,
)
_BEARER = re.compile(r"\bbearer\s+[^\s,;]+", re.IGNORECASE)
_TOKEN_CREDENTIAL = re.compile(r"\btoken\s+[^\s,;]+", re.IGNORECASE)
_SENSITIVE_TAIL = re.compile(
    r"\b(token|subscription_token|auth|authorization|provider_data|provider_payload|snapshot|snapshot_body|payload|body|uri|url|raw_uri|request_uri)\s*[:=].*$",
    re.IGNORECASE,
)
_SAFE_STRUCTURED_KEYS = frozenset(
    {
        "errorcode",
        "event",
        "latencyms",
        "metric",
        "ratelimited",
        "resourcekind",
        "sink",
        "status",
        "value",
    }
)
_SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "authtoken",
    "auth",
    "token",
    "providerdata",
    "providerpayload",
    "snapshot",
    "payload",
    "rawuri",
    "requesturi",
    "querystring",
    "query",
    "body",
    "headers",
    "cookie",
    "url",
    "uri",
)


class SubscriptionPathRedactionFilter(logging.Filter):
    """Prevent bearer subscription tokens from entering application logs."""

    def filter(self, record: logging.LogRecord) -> logging.LogRecord:
        sanitized = copy.copy(record)
        sanitized.msg = self._redact(record.msg)
        sanitized.args = self._redact(record.args)
        request = getattr(record, "request", None)
        if request is not None:
            sanitized.request = self._redact_request(request=request)
        if record.exc_info and record.exc_info[1] is not None:
            redacted = self._redact(str(record.exc_info[1]))
            sanitized.exc_info = (
                RuntimeError,
                RuntimeError(redacted),
                record.exc_info[2],
            )
            sanitized.exc_text = None
        return sanitized

    def _redact_request(self, *, request: Any) -> Any:
        sanitized = copy.copy(request)
        for attribute in ("path", "path_info"):
            value = getattr(request, attribute, None)
            if isinstance(value, str):
                setattr(sanitized, attribute, self._redact(value))
        original_meta = getattr(request, "META", None)
        if isinstance(original_meta, dict):
            sanitized.META = self._redact(original_meta)
            if _SAFE_PATH in getattr(sanitized, "path", ""):
                sanitized.META["QUERY_STRING"] = "[redacted]"
                sanitized.META["PATH_INFO"] = _SAFE_PATH
                for key in ("REQUEST_URI", "RAW_URI"):
                    if key in sanitized.META:
                        sanitized.META[key] = f"{_SAFE_PATH}?[redacted]"
        sanitized.GET = QueryDict("", mutable=False)
        sanitized._post = QueryDict("", mutable=False)
        sanitized._files = {}
        if "_body" in getattr(request, "__dict__", {}):
            sanitized._body = b"[redacted]"
        return sanitized

    def _redact(self, value: Any) -> Any:
        if isinstance(value, str):
            redacted = _SUBSCRIPTION_PATH.sub(_SAFE_PATH, value)
            redacted = _SUBSCRIPTION_QUERY.sub(r"\1?[redacted]", redacted)
            redacted = _VLESS_URI.sub("[redacted-vless-uri]", redacted)
            redacted = _UUID.sub(":uuid", redacted)
            redacted = _AUTHORIZATION.sub("auth=[redacted]", redacted)
            redacted = _BEARER.sub("bearer [redacted]", redacted)
            redacted = _TOKEN_CREDENTIAL.sub("token [redacted]", redacted)
            return _SENSITIVE_TAIL.sub(r"\1=[redacted]", redacted)
        if isinstance(value, tuple):
            return tuple(self._redact(item) for item in value)
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        if isinstance(value, dict):
            redacted: dict[Any, Any] = {}
            for key, item in value.items():
                normalized_key = re.sub(
                    r"[^a-z0-9]+", "_", str(key).casefold()
                ).strip("_")
                normalized = normalized_key.replace("_", "")
                is_safe = normalized in _SAFE_STRUCTURED_KEYS
                is_sensitive = any(
                    fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS
                )
                if is_sensitive and not is_safe:
                    redacted[normalized_key] = "[redacted]"
                else:
                    redacted[key] = self._redact(item)
            return redacted
        return value
