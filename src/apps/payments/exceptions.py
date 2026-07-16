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


class PaymentIntentNotFound(BaseServiceError):
    """Намерение платежа не найдено"""


class PaymentIntentMismatch(BaseServiceError):
    """Данные платежа не совпадают с выставленным счётом"""


class PaymentIntentExpired(BaseServiceError):
    """Срок действия счёта истёк"""


class PaymentIdentityConflict(BaseServiceError):
    """Идентификатор платежа уже связан с другими данными"""


class VPNProductNotConfigured(BaseServiceError):
    """VPN-продукт временно недоступен"""


class PaymentReceiptNotFound(BaseServiceError):
    """Квитанция платежа не найдена"""


class PaymentReceiptLeaseUnavailable(BaseServiceError):
    """Квитанция платежа уже обрабатывается"""


class PaymentReceiptDatabaseBusy(BaseServiceError):
    """База платежей временно занята"""
