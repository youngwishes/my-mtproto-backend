"""Хелперы интеграционного харнесса: клиенты бота, поллинг VDS, arrange/cleanup.

Импортировать ТОЛЬКО после того, как ``conftest`` поднял Django (он на sys.path
кладёт ``src``/``bot`` и зовёт ``django.setup()``).
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Awaitable, Callable
from urllib.parse import parse_qs, urlparse

import httpx
from django.conf import settings

# bot domain-клиенты (top-level пакет бота — ``src`` из bot/ на sys.path)
from src.core.backend_client import BackendClient
from src.domains.free_trial.client import FreeTrialClient
from src.domains.links.client import LinksClient
from src.domains.payments.client import PaymentsClient
from src.domains.referrals.client import ReferralsClient

from . import config


# --------------------------------------------------------------------------- #
# Клиенты бота, нацеленные на живой бэкенд                                     #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class BotClients:
    """Набор реальных domain-клиентов бота поверх одного BackendClient."""

    free_trial: FreeTrialClient
    referrals: ReferralsClient
    links: LinksClient
    payments: PaymentsClient


def make_clients() -> BotClients:
    backend = BackendClient(
        base_url=config.BACKEND_URL,
        auth_token=settings.BOT_AUTH_TOKEN,
    )
    return BotClients(
        free_trial=FreeTrialClient(backend=backend),
        referrals=ReferralsClient(backend=backend),
        links=LinksClient(backend=backend),
        payments=PaymentsClient(backend=backend, provider_token="test-provider"),
    )


# --------------------------------------------------------------------------- #
# Синтетические telegram_id                                                    #
# --------------------------------------------------------------------------- #
def make_test_id() -> str:
    """Безопасный синтетический telegram_id из зарезервированного диапазона."""
    return f"{config.TEST_ID_PREFIX}{random.randint(0, 999_999):06d}"


def assert_status(exc: object, code: str) -> None:
    """Проверить HTTP-статус внутри APIError бота (context['error'] = str(httpx exc)).

    Важно для error-path: APIError поднимается на ЛЮБОЙ не-2xx, поэтому без этой
    проверки 500 прошёл бы как «ожидаемая ошибка». Гард Telegram должен давать 400.
    """
    err = str(getattr(exc, "context", {}).get("error", ""))
    assert code in err, f"ожидался HTTP {code}, получено: {err!r}"


def expected_expired(days: int) -> str:
    """Ожидаемый expired_date (формат бэкенда %d.%m.%y) = сегодня (UTC) + days."""
    import datetime

    return (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    ).date().strftime("%d.%m.%y")


# --------------------------------------------------------------------------- #
# Поллинг async-доставки                                                       #
# --------------------------------------------------------------------------- #
async def wait_until(
    predicate: Callable[[], Awaitable[bool]],
    *,
    timeout: float = config.WAIT_TIMEOUT,
    interval: float = config.WAIT_INTERVAL,
) -> bool:
    """Опрашивать ``predicate`` пока не вернёт True или не выйдет таймаут."""
    deadline = time.monotonic() + timeout
    while True:
        if await predicate():
            return True
        if time.monotonic() >= deadline:
            return False
        await asyncio.sleep(interval)


# --------------------------------------------------------------------------- #
# Состояние секрета на VDS (через GET /api/users/{username})                   #
# --------------------------------------------------------------------------- #
async def vds_get(verify_url: str, username: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
        return await client.get(f"{verify_url}/api/users/{username}")


async def vds_has(verify_url: str, username: str) -> bool:
    """200 → секрет есть; 404 → нет."""
    resp = await vds_get(verify_url, username)
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    resp.raise_for_status()
    return False


def _parse_secret(link: str) -> str | None:
    """Достать query-параметр ``secret`` из tg://proxy ссылки."""
    qs = parse_qs(urlparse(link).query)
    values = qs.get("secret")
    return values[0] if values else None


async def vds_secret(verify_url: str, username: str) -> str | None:
    """Секрет (``secret=`` из поля ``link``) для сверки ротации; None если 404."""
    resp = await vds_get(verify_url, username)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return _parse_secret(resp.json().get("link", ""))


async def assert_present_on_all_vds(username: str, *, present: bool = True) -> None:
    """Проверить присутствие/отсутствие секрета на ВСЕХ настроенных VDS (с поллингом)."""
    for verify_url in config.VDS_VERIFY_URLS:
        ok = await wait_until(lambda u=verify_url: _matches(u, username, present))
        assert ok, (
            f"VDS {verify_url}: ожидалось present={present} для {username}, "
            f"не дождались за {config.WAIT_TIMEOUT}s"
        )


async def _matches(verify_url: str, username: str, present: bool) -> bool:
    return (await vds_has(verify_url, username)) is present


# --------------------------------------------------------------------------- #
# Teardown                                                                     #
# --------------------------------------------------------------------------- #
async def vds_delete(username: str) -> None:
    """Снести секрет пользователя со всех VDS (идемпотентно)."""
    for verify_url in config.VDS_VERIFY_URLS:
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            try:
                await client.request(
                    "DELETE",
                    f"{verify_url}/api/users",
                    json={"usernames": [username]},
                )
            except httpx.HTTPError:
                pass
