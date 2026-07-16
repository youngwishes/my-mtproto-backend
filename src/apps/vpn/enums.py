from __future__ import annotations

import enum


class _ChoicesEnum(enum.StrEnum):
    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]

    @property
    def label(self) -> str:
        labels = {
            "preparing": "Подготавливается",
            "ready": "Готов",
            "expired": "Истёк",
            "disabled_refund": "Отключён после возврата",
            "new": "Новая",
            "syncing": "Синхронизируется",
            "unhealthy": "Нездорова",
            "incompatible": "Несовместима",
            "over_capacity": "Переполнена",
            "pending": "Ожидает",
            "applied": "Применено",
            "failed": "Ошибка",
            "chrome": "Chrome",
            "xtls-rprx-vision": "XTLS Vision",
        }
        return labels[self.value]


class VPNAccessState(_ChoicesEnum):
    PREPARING = "preparing"
    READY = "ready"
    EXPIRED = "expired"
    DISABLED_REFUND = "disabled_refund"


class VPNNodeHealthState(_ChoicesEnum):
    NEW = "new"
    SYNCING = "syncing"
    READY = "ready"
    UNHEALTHY = "unhealthy"
    INCOMPATIBLE = "incompatible"
    OVER_CAPACITY = "over_capacity"


class VPNApplyStatus(_ChoicesEnum):
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"


class VPNRealityFingerprint(_ChoicesEnum):
    CHROME = "chrome"


class VPNRealityFlow(_ChoicesEnum):
    XTLS_RPRX_VISION = "xtls-rprx-vision"
