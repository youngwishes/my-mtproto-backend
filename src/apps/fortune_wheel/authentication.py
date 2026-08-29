from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from typing import final
from urllib.parse import parse_qsl

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class TelegramMiniAppPrincipal:
    telegram_id: str

    @property
    def is_authenticated(self) -> bool:
        return True


def _authentication_failed() -> AuthenticationFailed:
    return AuthenticationFailed("Некорректные данные Telegram Mini App.")


def validate_telegram_init_data(
    *,
    init_data: str,
    bot_token: str,
    now: datetime,
    max_age_seconds: int,
) -> TelegramMiniAppPrincipal:
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", None)
    if received_hash is None:
        raise _authentication_failed()

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise _authentication_failed()

    try:
        auth_date = int(values["auth_date"])
        telegram_id = str(json.loads(values["user"])["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _authentication_failed() from exc

    age_seconds = int(now.timestamp()) - auth_date
    if age_seconds < 0 or age_seconds > max_age_seconds:
        raise _authentication_failed()
    return TelegramMiniAppPrincipal(telegram_id=telegram_id)


class TelegramMiniAppAuthentication(BaseAuthentication):
    def authenticate(
        self,
        request: Request,
    ) -> tuple[TelegramMiniAppPrincipal, None]:
        init_data = request.headers.get("Telegram-Init-Data")
        if not init_data or not settings.BOT_TOKEN:
            raise _authentication_failed()
        principal = validate_telegram_init_data(
            init_data=init_data,
            bot_token=settings.BOT_TOKEN,
            now=timezone.now(),
            max_age_seconds=settings.FORTUNE_WHEEL_INIT_DATA_MAX_AGE_SECONDS,
        )
        return principal, None
