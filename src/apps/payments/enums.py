from __future__ import annotations

import enum


class PaymentProviderEnum(enum.StrEnum):
    YUKASSA = "yukassa"
    STARS = "stars"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(cls.YUKASSA, "ЮKassa"), (cls.STARS, "Telegram Stars")]


class PaymentKindEnum(enum.StrEnum):
    SUBSCRIPTION = "subscription"
    GIFT_CERTIFICATE = "gift_certificate"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [
            (cls.SUBSCRIPTION, "Подписка"),
            (cls.GIFT_CERTIFICATE, "Подарочный сертификат"),
        ]
