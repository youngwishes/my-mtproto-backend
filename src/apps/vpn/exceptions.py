from __future__ import annotations

from apps.core.exceptions import BaseServiceError


class VPNReissueUnavailable(BaseServiceError):
    """🔒 Перевыпуск VPN-ссылки доступен только после продления подписки."""


class VPNReissueCooldown(BaseServiceError):
    """🔒 Пожалуйста, подождите 5 минут с последнего обновления."""


class UnsupportedVPNProfileOperation(ValueError):
    """Неподдерживаемая операция доставки VPN-профиля."""
