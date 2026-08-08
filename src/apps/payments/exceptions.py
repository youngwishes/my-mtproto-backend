from __future__ import annotations

from apps.core.exceptions import BaseInfraError, BaseServiceError


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


class PlategaClientError(RuntimeError):
    """Safe internal Platega provider failure used by service mapping."""


class PlategaInvoiceCreationInProgress(BaseServiceError):
    """Счёт СБП уже создаётся. Повторите попытку через несколько секунд."""


class PlategaInvoiceUnavailable(BaseInfraError):
    """Не удалось создать счёт СБП. Попробуйте ещё раз."""


class CryptoInvoiceCreationInProgress(BaseServiceError):
    """Счёт уже создаётся. Повторите попытку через несколько секунд."""


class CryptoInvoiceUnavailable(BaseInfraError):
    """Не удалось создать счёт Crypto Pay. Попробуйте ещё раз."""


class CryptoPaymentRetryable(BaseInfraError):
    """Оплата подтверждена, выдача будет повторена автоматически."""
