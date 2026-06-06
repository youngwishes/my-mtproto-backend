from __future__ import annotations


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
