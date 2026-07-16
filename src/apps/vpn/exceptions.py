from __future__ import annotations

from apps.core.exceptions import BaseServiceError


class VPNAccessNotFound(BaseServiceError):
    """VPN-доступ не найден"""


class VPNAccessExpired(BaseServiceError):
    """Срок VPN-доступа истёк"""


class VPNReissueInProgress(BaseServiceError):
    """Перевыпуск VPN-доступа уже выполняется"""


class VPNCapacityUnavailable(BaseServiceError):
    """Сейчас нет доступных VPN-серверов"""
