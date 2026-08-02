from __future__ import annotations

from apps.core.exceptions import BaseServiceError


class BadPaymentData(BaseServiceError):
    """Некорректные данные платежа"""


class ProductNotFound(BaseServiceError):
    """Продукт не найден"""


class GiftCertificateNotFound(BaseServiceError):
    """Подарочный сертификат не найден"""


class GiftCertificateAlreadyActivated(BaseServiceError):
    """Подарочный сертификат уже активирован"""


class GiftCertificateExpired(BaseServiceError):
    """Срок действия подарочного сертификата истёк"""


class CryptoPayClientError(RuntimeError):
    """Safe internal provider failure used by service mapping/Celery retry."""
