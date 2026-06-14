from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from apps.core.exceptions import BaseInfraError, BaseServiceError
from apps.core.telegram.error_logger import (
    log_infra_error as _log_infra_error,
    log_service_error as _log_service_error,
)


def log_service_error(__call__: Callable) -> Callable:
    @wraps(__call__)
    def wrapper(self, **kwargs) -> Any:
        try:
            return __call__(self, **kwargs)
        except BaseServiceError as service_error:
            # Нотификация админа — best-effort: сбой Telegram не должен подменять
            # доменную ошибку (иначе бизнес-400 превратится в 500).
            try:
                _log_service_error(service_error)
            except Exception:
                pass
            raise service_error

    return wrapper


def log_infra_error(__call__: Callable) -> Callable:
    @wraps(__call__)
    def wrapper(self, **kwargs) -> Any:
        try:
            return __call__(self, **kwargs)
        except BaseInfraError as infra_error:
            from apps.notifications.services.send_notification_service import (
                SendNotificationService,
            )

            try:
                SendNotificationService(
                    slug="sorry_server_error", context={},
                )(chat_id=int(infra_error.telegram_id))
            except Exception:
                pass
            # Нотификация админа — best-effort, сбой Telegram не должен рушить запрос.
            try:
                _log_infra_error(infra_error)
            except Exception:
                pass
            raise infra_error

    return wrapper
