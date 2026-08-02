from __future__ import annotations

import enum


class ProductCodeEnum(enum.StrEnum):
    MTPROTO_30D = "mtproto_30d"
    VPN_30D = "vpn_30d"


class PaymentProviderEnum(enum.StrEnum):
    YUKASSA = "yukassa"
    STARS = "stars"
    CRYPTO_PAY = "crypto_pay"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [
            (cls.YUKASSA, "ЮKassa"),
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
