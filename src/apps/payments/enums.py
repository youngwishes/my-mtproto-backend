from __future__ import annotations

import enum


class PaymentProviderEnum(enum.StrEnum):
    YUKASSA = "yukassa"
    STARS = "stars"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(cls.YUKASSA, "ЮKassa"), (cls.STARS, "Telegram Stars")]
