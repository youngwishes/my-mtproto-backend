from __future__ import annotations

import enum


class ProductCodeEnum(enum.StrEnum):
    MTPROTO_30D = "mtproto_30d"
    VLESS_30D = "vless_30d"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [
            (cls.MTPROTO_30D, "MTProto, 30 дней"),
            (cls.VLESS_30D, "VLESS, 30 дней"),
        ]


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
