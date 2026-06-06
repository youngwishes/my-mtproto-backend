from __future__ import annotations

from typing import Any, Protocol


class IService(Protocol):
    def __call__(self, **kwargs) -> Any:
        """Business logic here. Use only keyword arguments."""
