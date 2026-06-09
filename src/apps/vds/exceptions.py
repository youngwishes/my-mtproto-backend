from __future__ import annotations

from apps.core.exceptions import BaseInfraError, BaseServiceError


class VDSNotAvailable(BaseInfraError):
    """VDS not available"""


class VDSConnectionLimit(BaseInfraError):
    """VDS connection limit"""


class KeyDoesNotExist(BaseServiceError):
    """🔒 У вас нет активного ключа. Если вы думаете, что это ошибка, пожалуйста, свяжитесь с нами через сообщения канала — @mtproto_keys."""


class TooManyRequests(BaseServiceError):
    """🔒 Пожалуйста, подождите 5 минут с последнего обновления."""
