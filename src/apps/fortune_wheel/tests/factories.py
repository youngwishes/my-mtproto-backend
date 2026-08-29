from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import urlencode

import factory

from apps.fortune_wheel.models import FortuneSpin


class FortuneSpinFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory("apps.users.tests.factories.SystemUserFactory")
    prize_apples = 15

    class Meta:
        model = FortuneSpin


def make_telegram_init_data(
    *,
    bot_token: str,
    user_id: int,
    auth_date: int,
) -> str:
    values = {
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(
            {"id": user_id, "first_name": "Test", "username": "tester"},
            separators=(",", ":"),
        ),
    }
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    values["hash"] = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(values)
