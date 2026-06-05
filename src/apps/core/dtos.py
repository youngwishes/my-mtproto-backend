from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(kw_only=True, frozen=True, slots=True)
class BaseServiceDTO:
    """Базовый DTO для передачи данных между слоями."""

    def asdict(self) -> dict:
        return asdict(self)
