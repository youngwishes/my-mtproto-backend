from __future__ import annotations

import enum


class MailingStatus(enum.IntEnum):
    DRAFT = 1
    SENDING = 2
    COMPLETED = 3
    FAILED = 4
    PARTIALLY_COMPLETED = 5

    @classmethod
    def choices(cls) -> list[tuple[int, str]]:
        return [
            (cls.DRAFT, "Черновик"),
            (cls.SENDING, "Отправляется"),
            (cls.COMPLETED, "Завершена"),
            (cls.FAILED, "Ошибка"),
            (cls.PARTIALLY_COMPLETED, "Частично завершена"),
        ]


class FilterType(enum.IntEnum):
    ALL_ACTIVE = 1
    EXPIRING_SOON = 2
    NOT_SUBSCRIBED = 3

    @classmethod
    def choices(cls) -> list[tuple[int, str]]:
        return [
            (cls.ALL_ACTIVE, "Все активные пользователи"),
            (cls.EXPIRING_SOON, "Ключ истекает скоро"),
            (cls.NOT_SUBSCRIBED, "Не подписаны на канал"),
        ]


class ContextResolverType(enum.IntEnum):
    NONE = 0
    ACTIVE_KEY_LINK = 1

    @classmethod
    def choices(cls) -> list[tuple[int, str]]:
        return [
            (cls.NONE, "Без персонального контекста"),
            (cls.ACTIVE_KEY_LINK, "Ссылка на активный ключ"),
        ]
