from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

_MOSCOW_TIMEZONE = ZoneInfo("Europe/Moscow")
_DATE_INPUT_FORMATS = ("%Y-%m-%d", "%d.%m.%y", "%d.%m.%Y")


def format_user_date(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        for input_format in _DATE_INPUT_FORMATS:
            try:
                parsed = datetime.strptime(value, input_format).date()
            except ValueError:
                continue
            break
        else:
            return value
    return parsed.strftime("%d.%m.%Y")


def format_user_local_date(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(_MOSCOW_TIMEZONE).strftime("%d.%m.%Y")


def format_user_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    localized = value.astimezone(_MOSCOW_TIMEZONE)
    return localized.strftime("%d.%m.%Y, %H:%M МСК")
