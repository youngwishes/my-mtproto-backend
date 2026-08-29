from __future__ import annotations

from apps.core.exceptions import BaseInfraError, BaseServiceError


class FortuneWheelRegistrationRequired(BaseServiceError):
    """Сначала примите условия использования в Telegram-боте."""


class FortuneWheelCooldown(BaseServiceError):
    """Следующее вращение пока недоступно."""


class FortuneWheelRetryable(BaseInfraError):
    """Не удалось выполнить вращение. Попробуйте ещё раз."""
