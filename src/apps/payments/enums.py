from __future__ import annotations

import enum


class ProductCodeEnum(enum.StrEnum):
    MTPROTO_30D = "mtproto_30d"
    VPN_30D = "vpn_30d"


class PaymentProviderEnum(enum.StrEnum):
    STARS = "stars"
    CRYPTO_PAY = "crypto_pay"
    PLATEGA = "platega"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [
            (cls.STARS, "Telegram Stars"),
            (cls.CRYPTO_PAY, "Crypto Pay"),
            (cls.PLATEGA, "Platega"),
        ]


class PaymentMethodCodeEnum(enum.StrEnum):
    PLATEGA_SBP = "platega_sbp"
    STARS = "stars"
    CRYPTO_PAY = "crypto_pay"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [
            (cls.PLATEGA_SBP, "СБП"),
            (cls.STARS, "Telegram Stars"),
            (cls.CRYPTO_PAY, "Crypto Pay"),
        ]


class PaymentKindEnum(enum.StrEnum):
    SUBSCRIPTION = "subscription"
    VPN_SUBSCRIPTION = "vpn_subscription"
    GIFT_CERTIFICATE = "gift_certificate"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [
            (cls.SUBSCRIPTION, "Подписка"),
            (cls.VPN_SUBSCRIPTION, "VPN-подписка"),
            (cls.GIFT_CERTIFICATE, "Подарочный сертификат"),
        ]


class AppleRedemptionModeEnum(enum.StrEnum):
    ONE_DAY = "one_day"
    ALL = "all"


class CryptoPaymentIntentStatusEnum(enum.StrEnum):
    CREATING = "creating"
    ACTIVE = "active"
    LOCAL_EXPIRED = "local_expired"
    PROCESSING = "processing"
    RETRYABLE = "retryable"
    FULFILLED = "fulfilled"
    CREATE_FAILED = "create_failed"
    PROVIDER_EXPIRED = "provider_expired"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(status, status.value) for status in cls]


class PlategaPaymentIntentStatusEnum(enum.StrEnum):
    CREATING = "creating"
    ACTIVE = "active"
    LOCAL_EXPIRED = "local_expired"
    PROCESSING = "processing"
    RETRYABLE = "retryable"
    PROVIDER_CANCELED = "provider_canceled"
    CREATE_FAILED = "create_failed"
    FULFILLED = "fulfilled"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(status, status.value) for status in cls]
