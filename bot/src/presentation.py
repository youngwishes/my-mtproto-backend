from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

_MOSCOW_TIMEZONE = ZoneInfo("Europe/Moscow")
_DATE_INPUT_FORMATS = ("%Y-%m-%d", "%d.%m.%y", "%d.%m.%Y")


def format_user_date(value: str) -> str:
    for input_format in _DATE_INPUT_FORMATS:
        try:
            parsed = datetime.strptime(value, input_format)
        except ValueError:
            continue
        return parsed.strftime("%d.%m.%Y")

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(_MOSCOW_TIMEZONE).strftime("%d.%m.%Y")


def format_user_datetime(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    localized = parsed.astimezone(_MOSCOW_TIMEZONE)
    return localized.strftime("%d.%m.%Y, %H:%M МСК")


def format_rub_amount(value: str) -> str:
    amount = Decimal(value).quantize(Decimal("0.01"))
    if amount == amount.to_integral_value():
        return format(amount, ".0f")
    return format(amount, ".2f").replace(".", ",")
