import logging
from functools import wraps
from typing import Any, Callable, Protocol

from apps.core.bot import TelegramBot

logger = logging.LoggerAdapter(
    logging.getLogger(__name__), extra={"tag": "service-layer"}
)


class IService(Protocol):
    def __call__(self, **kwargs) -> Any:
        """Business logic here. Use only keyword arguments."""


class BaseError(Exception):
    def __init__(
        self, telegram_id: int | str | list[int | str], message: str = None, **context
    ) -> None:
        self.telegram_id = telegram_id
        self.message = message or self.__doc__
        self.context = context

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "telegram_id": self.telegram_id,
            "context": self.context,
        }


class BaseServiceError(BaseError): ...


class BaseInfraError(BaseError): ...


def log_service_error(__call__: Callable) -> Callable:
    @wraps(__call__)
    def wrapper(self, **kwargs) -> Any:
        try:
            return __call__(self, **kwargs)
        except BaseServiceError as service_error:
            TelegramBot().log_service_error(service_error)
            raise service_error

    return wrapper


def log_infra_error(__call__: Callable) -> Callable:
    @wraps(__call__)
    def wrapper(self, **kwargs) -> Any:
        try:
            return __call__(self, **kwargs)
        except BaseInfraError as infra_error:
            TelegramBot().send_sorry(infra_error)
            TelegramBot().log_infra_error(infra_error)
            raise infra_error

    return wrapper
