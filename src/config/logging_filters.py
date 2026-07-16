from __future__ import annotations

import logging
import re
from typing import Any

from django.http import QueryDict


_SUBSCRIPTION_PATH = re.compile(r"/api/v1/vpn/subscriptions/[^/?\s]+/?")
_SAFE_PATH = "/api/v1/vpn/subscriptions/:token/"
_SUBSCRIPTION_QUERY = re.compile(
    r"(/api/v1/vpn/subscriptions/:token/)\?[^\s'\"]*"
)


class SubscriptionPathRedactionFilter(logging.Filter):
    """Prevent bearer subscription tokens from entering application logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _SUBSCRIPTION_PATH.sub(_SAFE_PATH, record.msg)
        record.args = self._redact(record.args)
        request = getattr(record, "request", None)
        if request is not None:
            for attribute in ("path", "path_info"):
                value = getattr(request, attribute, None)
                if isinstance(value, str):
                    setattr(request, attribute, self._redact(value))
            meta = getattr(request, "META", None)
            if isinstance(meta, dict):
                for key in ("REQUEST_URI", "RAW_URI"):
                    if isinstance(meta.get(key), str):
                        meta[key] = self._redact(meta[key])
                if _SAFE_PATH in getattr(request, "path", ""):
                    meta["QUERY_STRING"] = "[redacted]"
                    meta["PATH_INFO"] = _SAFE_PATH
                    if "GET" in getattr(request, "__dict__", {}):
                        request.GET = QueryDict("", mutable=False)
                    for key in ("REQUEST_URI", "RAW_URI"):
                        if key in meta:
                            meta[key] = f"{_SAFE_PATH}?[redacted]"
        if record.exc_info and record.exc_info[1] is not None:
            redacted = self._redact(str(record.exc_info[1]))
            record.exc_info = (RuntimeError, RuntimeError(redacted), record.exc_info[2])
            record.exc_text = None
        return True

    def _redact(self, value: Any) -> Any:
        if isinstance(value, str):
            redacted = _SUBSCRIPTION_PATH.sub(_SAFE_PATH, value)
            return _SUBSCRIPTION_QUERY.sub(r"\1?[redacted]", redacted)
        if isinstance(value, tuple):
            return tuple(self._redact(item) for item in value)
        if isinstance(value, dict):
            return {key: self._redact(item) for key, item in value.items()}
        return value
