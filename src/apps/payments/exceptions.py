from apps.core.exceptions import BaseServiceError


class BadPaymentData(BaseServiceError):
    """Некорректные данные платежа"""


class ProductNotFound(BaseServiceError):
    """Продукт не найден"""
