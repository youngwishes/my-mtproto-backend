from apps.core.service import BaseServiceError


class BadPaymentData(BaseServiceError):
    """Некорректные данные платежа"""


class ProductNotFound(BaseServiceError):
    """Продукт не найден"""
