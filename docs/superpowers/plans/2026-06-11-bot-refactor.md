# Bot Domain-Driven Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `bot/src/` from a flat layout into isolated domain modules (`free_trial`, `payments`, `referrals`, `links`) with a shared `core/` transport layer.

**Architecture:** Each domain lives in `domains/<name>/` with its own `client.py`, `handlers.py`, and `messages.py`. A shared `BackendClient` in `core/` centralises httpx calls, auth headers, and error parsing. Domain clients use `BackendClient` via composition; a factory function wires each client.

**Tech Stack:** Python 3.13, aiogram 3.x, httpx, pytest, pytest-asyncio, respx (httpx mock)

**Spec:** `docs/superpowers/specs/2026-06-11-bot-refactor-design.md`

---

## File Map

**Create:**
```
bot/src/core/__init__.py
bot/src/core/config.py
bot/src/core/exceptions.py
bot/src/core/handle_error.py
bot/src/core/backend_client.py
bot/src/domains/__init__.py
bot/src/domains/free_trial/__init__.py
bot/src/domains/free_trial/enums.py
bot/src/domains/free_trial/messages.py
bot/src/domains/free_trial/client.py
bot/src/domains/free_trial/handlers.py
bot/src/domains/payments/__init__.py
bot/src/domains/payments/messages.py
bot/src/domains/payments/client.py
bot/src/domains/payments/handlers.py
bot/src/domains/referrals/__init__.py
bot/src/domains/referrals/messages.py
bot/src/domains/referrals/client.py
bot/src/domains/referrals/handlers.py
bot/src/domains/links/__init__.py
bot/src/domains/links/messages.py
bot/src/domains/links/client.py
bot/src/domains/links/handlers.py
bot/src/router.py
bot/src/main.py
bot/tests/__init__.py
bot/tests/conftest.py
bot/tests/core/__init__.py
bot/tests/core/test_backend_client.py
bot/tests/domains/__init__.py
bot/tests/domains/free_trial/__init__.py
bot/tests/domains/free_trial/test_client.py
bot/tests/domains/payments/__init__.py
bot/tests/domains/payments/test_client.py
bot/tests/domains/referrals/__init__.py
bot/tests/domains/referrals/test_client.py
bot/tests/domains/links/__init__.py
bot/tests/domains/links/test_client.py
```

**Modify:**
```
bot/pyproject.toml           — add pytest/pytest-asyncio/respx dev deps
bot/src/bot.py               — strip to Bot instance only
```

**Delete (Task 9 only):**
```
bot/src/handlers.py
bot/src/messages.py
bot/src/enums.py
bot/src/config.py
bot/src/exceptions.py
bot/src/services/            — entire directory
```

---

## Task 1: Test Infrastructure

**Files:**
- Modify: `bot/pyproject.toml`
- Create: `bot/tests/__init__.py`, `bot/tests/conftest.py`

- [ ] **Step 1: Add dev dependencies to pyproject.toml**

Open `bot/pyproject.toml` and add after the `[project]` section:

```toml
[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "respx>=0.21",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Install dev deps**

```bash
cd bot && uv sync --group dev
```

Expected: lock file updated, deps installed.

- [ ] **Step 3: Create tests/ package and conftest**

Create `bot/tests/__init__.py` — empty file.

Create `bot/tests/conftest.py`:
```python
import os

# Set env vars before any module import that reads them
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:test_token")
os.environ.setdefault("API_URL", "http://test.api")
os.environ.setdefault("BOT_AUTH_TOKEN", "test-bot-auth")
os.environ.setdefault("MY_TELEGRAM_ID", "99999")
os.environ.setdefault("PROVIDER_TOKEN", "test-provider")
```

- [ ] **Step 4: Verify pytest works**

```bash
cd bot && uv run pytest --collect-only
```

Expected: `no tests ran` — no errors, just empty collection.

- [ ] **Step 5: Commit**

```bash
git add bot/pyproject.toml bot/tests/
git commit -m "test: set up pytest infrastructure for bot"
```

---

## Task 2: core/ — config, exceptions, handle_error

**Files:**
- Create: `bot/src/core/__init__.py`, `bot/src/core/config.py`, `bot/src/core/exceptions.py`, `bot/src/core/handle_error.py`

- [ ] **Step 1: Create core/ package**

Create `bot/src/core/__init__.py` — empty file.

- [ ] **Step 2: Create core/config.py**

```python
from __future__ import annotations

import os

BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL: str = os.getenv("API_URL")
MY_TELEGRAM_ID: str = os.getenv("MY_TELEGRAM_ID")
BOT_AUTH_TOKEN: str = os.getenv("BOT_AUTH_TOKEN")
PROVIDER_TOKEN: str = os.getenv("PROVIDER_TOKEN")
```

- [ ] **Step 3: Create core/exceptions.py**

```python
from __future__ import annotations


class BaseServiceError(Exception):
    def __init__(
        self,
        telegram_id: int | str | list[int | str],
        message: str = None,
        **context,
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


class APIError(BaseServiceError):
    """MTPRoto API not available now. Please try again later."""
```

- [ ] **Step 4: Create core/handle_error.py**

```python
from __future__ import annotations

import html
import json
from collections.abc import Callable
from typing import Any

from bot import bot
from core.config import MY_TELEGRAM_ID
from core.exceptions import BaseServiceError


def log_service_error(__call__: Callable) -> Callable:
    async def wrapped(self, **kwargs) -> Any:
        try:
            return await __call__(self, **kwargs)
        except BaseServiceError as exc:
            await bot.send_message(
                chat_id=exc.telegram_id,
                text=exc.message,
            )
            pretty_error = json.dumps(exc.to_dict(), indent=2, ensure_ascii=False)
            escaped_error = html.escape(pretty_error)
            await bot.send_message(
                chat_id=MY_TELEGRAM_ID,
                text=(
                    "🟡 <b>(BOT) Системное оповещение</b>\n\n"
                    "🛡 <b>Тип ошибки:</b> SERVICE\n"
                    "📋 <b>Детали:</b>\n"
                    f"<code>{escaped_error}</code>\n\n"
                    "⚙️ <i>Требуется внимание команды</i>"
                ),
                parse_mode="HTML",
            )
            raise exc

    return wrapped
```

- [ ] **Step 5: Commit**

```bash
git add bot/src/core/
git commit -m "refactor(bot): add core/ layer with config, exceptions, handle_error"
```

---

## Task 3: BackendClient (TDD)

**Files:**
- Create: `bot/src/core/backend_client.py`
- Create: `bot/tests/core/__init__.py`, `bot/tests/core/test_backend_client.py`

- [ ] **Step 1: Create test package**

Create `bot/tests/core/__init__.py` — empty file.

- [ ] **Step 2: Write failing tests**

Create `bot/tests/core/test_backend_client.py`:

```python
from __future__ import annotations

import pytest
import httpx
import respx

from core.backend_client import BackendClient
from core.exceptions import APIError


@respx.mock
async def test_post_returns_json_on_success():
    respx.post("http://test.api/api/v1/users/test/").mock(
        return_value=httpx.Response(200, json={"available_free_period": "MONTH"})
    )
    client = BackendClient()
    result = await client.post(
        path="/api/v1/users/test/",
        telegram_id="123",
        data={"username": "123"},
    )
    assert result == {"available_free_period": "MONTH"}


@respx.mock
async def test_post_sends_auth_header():
    route = respx.post("http://test.api/api/v1/users/test/").mock(
        return_value=httpx.Response(200, json={})
    )
    await BackendClient().post(
        path="/api/v1/users/test/",
        telegram_id="123",
        data={},
    )
    assert route.calls[0].request.headers["bot-auth-token"] == "test-bot-auth"


@respx.mock
async def test_post_raises_api_error_with_message_on_http_error_with_body():
    respx.post("http://test.api/api/v1/users/test/").mock(
        return_value=httpx.Response(400, json={"error": "user not found"})
    )
    with pytest.raises(APIError) as exc_info:
        await BackendClient().post(
            path="/api/v1/users/test/",
            telegram_id="123",
            data={},
        )
    assert exc_info.value.message == "user not found"
    assert exc_info.value.telegram_id == "123"


@respx.mock
async def test_post_raises_api_error_without_message_on_network_error():
    respx.post("http://test.api/api/v1/users/test/").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    with pytest.raises(APIError) as exc_info:
        await BackendClient().post(
            path="/api/v1/users/test/",
            telegram_id="123",
            data={},
        )
    assert exc_info.value.telegram_id == "123"


@respx.mock
async def test_get_returns_json_on_success():
    respx.get("http://test.api/api/v1/payments/").mock(
        return_value=httpx.Response(200, json={"title": "BeatVault", "price": 7900})
    )
    client = BackendClient()
    result = await client.get(path="/api/v1/payments/")
    assert result == {"title": "BeatVault", "price": 7900}
```

- [ ] **Step 3: Run tests — confirm they fail**

```bash
cd bot && uv run pytest tests/core/test_backend_client.py -v
```

Expected: `ImportError: cannot import name 'BackendClient' from 'core.backend_client'` (module doesn't exist yet).

- [ ] **Step 4: Implement BackendClient**

Create `bot/src/core/backend_client.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import final

import httpx

from core import config
from core.exceptions import APIError


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class BackendClient:
    async def post(self, *, path: str, telegram_id: str, data: dict) -> dict:
        url = config.API_URL + path
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    data=data,
                    headers={"Bot-Auth-Token": config.BOT_AUTH_TOKEN},
                )
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            try:
                body = json.loads(exc.response.content)
            except Exception:
                raise APIError(
                    telegram_id=telegram_id,
                    request_url=url,
                    error=str(exc),
                )
            else:
                raise APIError(
                    telegram_id=telegram_id,
                    request_url=url,
                    error=str(exc),
                    message=body.get("error"),
                )

    async def get(
        self,
        *,
        path: str,
        telegram_id: str | None = None,
        params: dict | None = None,
    ) -> dict:
        url = config.API_URL + path
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    params=params or {},
                    headers={"Bot-Auth-Token": config.BOT_AUTH_TOKEN},
                )
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            try:
                body = json.loads(exc.response.content)
            except Exception:
                raise APIError(
                    telegram_id=telegram_id or "unknown",
                    request_url=url,
                    error=str(exc),
                )
            else:
                raise APIError(
                    telegram_id=telegram_id or "unknown",
                    request_url=url,
                    error=str(exc),
                    message=body.get("error"),
                )
```

- [ ] **Step 5: Run tests — confirm they pass**

```bash
cd bot && uv run pytest tests/core/test_backend_client.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add bot/src/core/backend_client.py bot/tests/core/
git commit -m "feat(bot): add BackendClient with unified HTTP transport"
```

---

## Task 4: free_trial Domain

**Files:**
- Create: `bot/src/domains/__init__.py`, `bot/src/domains/free_trial/__init__.py`
- Create: `bot/src/domains/free_trial/enums.py`
- Create: `bot/src/domains/free_trial/messages.py`
- Create: `bot/src/domains/free_trial/client.py`
- Create: `bot/src/domains/free_trial/handlers.py`
- Create: `bot/tests/domains/__init__.py`, `bot/tests/domains/free_trial/__init__.py`
- Create: `bot/tests/domains/free_trial/test_client.py`

- [ ] **Step 1: Create domain package files**

Create `bot/src/domains/__init__.py` — empty.
Create `bot/src/domains/free_trial/__init__.py` — empty.
Create `bot/tests/domains/__init__.py` — empty.
Create `bot/tests/domains/free_trial/__init__.py` — empty.

- [ ] **Step 2: Create free_trial/enums.py**

```python
from __future__ import annotations

from enum import StrEnum


class FreeAvailable(StrEnum):
    MONTH = "MONTH"
    TWO_WEEK = "TWO_WEEK"
    WEEK = "WEEK"
    NOT_AVAILABLE = "NOT_AVAILABLE"
```

- [ ] **Step 3: Create free_trial/messages.py**

```python
from __future__ import annotations

from domains.free_trial.enums import FreeAvailable

WELCOME_TEXT_MONTH = """
🚀 <b>Привет! Я помогу ускорить твой Telegram</b>

С MTPRoto твой Telegram будет летать даже при плохом интернете:
• 📱 Загрузка медиа за секунды
• 🎥 Видео без буферизации
• 🔒 Безопасное соединение
• ⚡️ Стабильная работа 24/7

<b>👇 Первый месяц — в подарок!</b>
"""

WELCOME_TEXT_WEEK = """
🚀 <b>Привет! Я помогу ускорить твой Telegram</b>

С MTPRoto твой Telegram будет летать даже при плохом интернете:
• 📱 Загрузка медиа за секунды
• 🎥 Видео без буферизации
• 🔒 Безопасное соединение
• ⚡️ Стабильная работа 24/7

<b>👇 Первая неделя — в подарок!</b>
"""

WELCOME_TEXT_TWO_WEEK = """
🚀 <b>Привет! Я помогу ускорить твой Telegram</b>

С MTPRoto твой Telegram будет летать даже при плохом интернете:
• 📱 Загрузка медиа за секунды
• 🎥 Видео без буферизации
• 🔒 Безопасное соединение
• ⚡️ Стабильная работа 24/7

👀 Вижу, что ты пришел по ссылке от друга!

<b>👇 Первые 2 недели — в подарок!</b>
"""

WELCOME_TEXT_NOT_FREE = """
🚀 <b>Привет! Я помогу ускорить твой Telegram</b>

С MTPRoto твой Telegram будет летать даже при плохом интернете:
• 📱 Загрузка медиа за секунды
• 🎥 Видео без буферизации
• 🔒 Безопасное соединение
• ⚡️ Стабильная работа 24/7

<b>👇 Жми «ускорить»!</b>
"""

FREE_AVAILABLE_TEXT_MAPPING = {
    FreeAvailable.MONTH: WELCOME_TEXT_MONTH,
    FreeAvailable.WEEK: WELCOME_TEXT_WEEK,
    FreeAvailable.TWO_WEEK: WELCOME_TEXT_TWO_WEEK,
    FreeAvailable.NOT_AVAILABLE: WELCOME_TEXT_NOT_FREE,
}

KEY_GENERATED_TEXT = """
🎉 <b>Твой персональный ключ готов!</b>

🔑 Ключ находится в кнопке, прикрепленной к этому сообщению.

📝 <b>Как активировать:</b>
1. Нажми на ссылку в кнопке ниже
2. Нажми «подключить»

✅ <b>Готово!</b> Telegram теперь работает быстрее

⏳ Сссылка действительна до: <b>{expired_date}</b>

<i>🤝 Чтобы быть в курсе всех новостей, пожалуйста, подпишись на наш канал — @mtproto_keys</i>
"""

FAQ_TEXT = """
❓ <b>Часто задаваемые вопросы:</b>

<b>1. Это законно?</b>
✅ Да, MTPRoto — это легальный прокси-сервис, <b>встроенный</b> в эко-систему Telegram.

<b>2. А если не заработает?</b>
🛠 Мы даем бесплатную <b>неделю</b> на тест. Не понравится — просто не покупай.

<b>3. На сколько устройств хватит?</b>
📱 Один ключ работает на трех устройствах (для связки — телефон + ПК + планшет)

<b>4. Нужно ли что-то устанавливать?</b>
🔧 Нет, только вставить ключ в настройках Telegram

<b>5. Какая скорость?</b>
⚡️ Ограничений нет, только возможности твоего интернета

<b>6. Какие способы оплаты?</b>
💳 Банковская карта, SberPay, ЮMoney, ⭐ Telegram Stars

Остались вопросы? Напиши @mtproto_keys
"""
```

- [ ] **Step 4: Write failing tests for FreeTrialClient**

Create `bot/tests/domains/free_trial/test_client.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from domains.free_trial.client import FreeLink, FreeTrialClient, get_free_trial_client


async def test_check_eligibility_returns_available_period():
    mock_http = AsyncMock()
    mock_http.post.return_value = {"available_free_period": "MONTH"}
    client = FreeTrialClient(_http=mock_http)

    result = await client.check_eligibility(
        telegram_id="123",
        telegram_username="testuser",
    )

    assert result == "MONTH"
    mock_http.post.assert_called_once_with(
        path="/api/v1/users/check-first-free-link/",
        telegram_id="123",
        data={"username": "123", "telegram_username": "testuser"},
    )


async def test_check_eligibility_includes_referrer_when_provided():
    mock_http = AsyncMock()
    mock_http.post.return_value = {"available_free_period": "TWO_WEEK"}
    client = FreeTrialClient(_http=mock_http)

    await client.check_eligibility(
        telegram_id="123",
        telegram_username="testuser",
        invited_from_username="456",
    )

    call_data = mock_http.post.call_args.kwargs["data"]
    assert call_data["invited_from_username"] == "456"


async def test_activate_returns_free_link():
    mock_http = AsyncMock()
    mock_http.post.return_value = {
        "link": "https://t.me/proxy?server=1.2.3.4",
        "expired_date": "2026-07-11",
    }
    client = FreeTrialClient(_http=mock_http)

    result = await client.activate(telegram_id="123")

    assert isinstance(result, FreeLink)
    assert result.link == "https://t.me/proxy?server=1.2.3.4"
    assert result.expired_date == "2026-07-11"


def test_get_free_trial_client_returns_instance():
    client = get_free_trial_client()
    assert isinstance(client, FreeTrialClient)
```

- [ ] **Step 5: Run tests — confirm they fail**

```bash
cd bot && uv run pytest tests/domains/free_trial/test_client.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 6: Implement free_trial/client.py**

Create `bot/src/domains/free_trial/client.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import final

from core.backend_client import BackendClient
from core.handle_error import log_service_error


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FreeLink:
    link: str
    expired_date: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FreeTrialClient:
    _http: BackendClient = field(default_factory=BackendClient)

    @log_service_error
    async def check_eligibility(
        self,
        *,
        telegram_id: str,
        telegram_username: str,
        invited_from_username: str | None = None,
    ) -> str:
        data: dict = {"username": telegram_id, "telegram_username": telegram_username}
        if invited_from_username is not None:
            data["invited_from_username"] = invited_from_username
        result = await self._http.post(
            path="/api/v1/users/check-first-free-link/",
            telegram_id=telegram_id,
            data=data,
        )
        return result["available_free_period"]

    @log_service_error
    async def activate(self, *, telegram_id: str) -> FreeLink:
        result = await self._http.post(
            path="/api/v1/users/first-free-link/",
            telegram_id=telegram_id,
            data={"username": telegram_id},
        )
        return FreeLink(**result)


def get_free_trial_client() -> FreeTrialClient:
    return FreeTrialClient()
```

- [ ] **Step 7: Run tests — confirm they pass**

```bash
cd bot && uv run pytest tests/domains/free_trial/test_client.py -v
```

Expected: 4 passed.

- [ ] **Step 8: Create free_trial/handlers.py**

```python
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from domains.free_trial.client import get_free_trial_client
from domains.free_trial.enums import FreeAvailable
from domains.free_trial.messages import (
    FAQ_TEXT,
    FREE_AVAILABLE_TEXT_MAPPING,
    KEY_GENERATED_TEXT,
)

router = Router()


def _build_start_keyboard(available_free_period: str) -> InlineKeyboardMarkup:
    callback_data = (
        "boost_free"
        if available_free_period != FreeAvailable.NOT_AVAILABLE
        else "boost_paid"
    )
    keyboard = InlineKeyboardBuilder(
        markup=[
            [InlineKeyboardButton(text="⚡️ Ускорить Telegram", callback_data=callback_data)],
            [InlineKeyboardButton(text="📋 Информация", callback_data="info")],
            [InlineKeyboardButton(text="🤝 Реферальный кабинет", callback_data="referral")],
            [InlineKeyboardButton(text="🔄 Перевыпустить ссылку", callback_data="update_link")],
        ],
    )
    return keyboard.adjust(1).as_markup()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    invited_from_username = None
    try:
        referrer_id = int(message.text.split()[-1])
        if referrer_id != message.from_user.id:
            invited_from_username = str(referrer_id)
    except ValueError:
        pass

    client = get_free_trial_client()
    available_free_period = await client.check_eligibility(
        telegram_id=str(message.from_user.id),
        telegram_username=str(getattr(message.from_user, "username", None)),
        invited_from_username=invited_from_username,
    )
    await message.answer(
        text=FREE_AVAILABLE_TEXT_MAPPING.get(available_free_period),
        reply_markup=_build_start_keyboard(available_free_period),
    )


@router.callback_query(F.data == "show_start_screen")
async def cmd_start_inline(callback: CallbackQuery) -> None:
    client = get_free_trial_client()
    available_free_period = await client.check_eligibility(
        telegram_id=str(callback.message.chat.id),
        telegram_username=str(getattr(callback.message.from_user, "username", None)),
    )
    await callback.message.edit_text(
        text=FREE_AVAILABLE_TEXT_MAPPING.get(available_free_period),
        reply_markup=_build_start_keyboard(available_free_period),
    )


@router.callback_query(F.data == "boost_free")
async def process_boost_free(callback: CallbackQuery) -> None:
    await callback.answer()
    client = get_free_trial_client()
    response = await client.activate(telegram_id=str(callback.message.chat.id))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇳🇱 Подключиться", url=response.link)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")],
        ]
    )
    await callback.message.edit_text(
        text=KEY_GENERATED_TEXT.format(expired_date=response.expired_date),
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "info")
async def process_info(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        text=FAQ_TEXT,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👀 Договор-оферта",
                        url="https://drive.google.com/file/d/13GI1ZuKBm4nZkNxESOokGM6fTAAxaCs7/view?usp=sharing",
                    )
                ],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")],
            ]
        ),
    )
```

- [ ] **Step 9: Commit**

```bash
git add bot/src/domains/ bot/tests/domains/
git commit -m "feat(bot): add free_trial domain with client, handlers, messages, enums"
```

---

## Task 5: payments Domain

**Files:**
- Create: `bot/src/domains/payments/__init__.py`, `bot/src/domains/payments/messages.py`
- Create: `bot/src/domains/payments/client.py`, `bot/src/domains/payments/handlers.py`
- Create: `bot/tests/domains/payments/__init__.py`, `bot/tests/domains/payments/test_client.py`

- [ ] **Step 1: Create packages**

Create `bot/src/domains/payments/__init__.py` — empty.
Create `bot/tests/domains/payments/__init__.py` — empty.

- [ ] **Step 2: Create payments/messages.py**

```python
from __future__ import annotations

PAYMENT_SELECTION_TEXT = (
    "💰 <b>Выберите способ оплаты</b>\n\n"
    "• 💳 <b>ЮKassa</b> — 79 ₽/месяц\n"
    "  Банковская карта, SberPay, ЮMoney\n\n"
    "• ⭐ <b>Telegram Stars</b> — 60 ★/месяц\n"
    "  Оплата прямо в Telegram\n"
)

PAYMENT_ERROR_TEXT = (
    "⚠️ Оплата получена, но произошла ошибка при выдаче ключа.\n"
    "Пожалуйста, обратитесь в поддержку: @mtproto_keys"
)
```

- [ ] **Step 3: Write failing tests for PaymentsClient**

Create `bot/tests/domains/payments/test_client.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import LabeledPrice

from domains.payments.client import (
    InvoiceData,
    PaymentsClient,
    StarsInvoiceData,
    get_payments_client,
)


async def test_get_invoice_data_returns_invoice():
    mock_http = AsyncMock()
    mock_http.get.return_value = {
        "title": "BeatVault",
        "description": "MTProto proxy",
        "currency": "RUB",
        "price": 7900,
        "stars_price": 60,
        "provider_data": {"key": "value"},
        "send_email_to_provider": False,
        "need_email": False,
    }
    with patch("domains.payments.client.config") as mock_config:
        mock_config.PROVIDER_TOKEN = "test-provider"
        client = PaymentsClient(_http=mock_http)
        result = await client.get_invoice_data()

    assert isinstance(result, InvoiceData)
    assert result.title == "BeatVault"
    assert result.currency == "RUB"
    assert result.provider_token == "test-provider"
    assert len(result.prices) == 1
    assert isinstance(result.prices[0], LabeledPrice)
    assert result.prices[0].amount == 7900


async def test_get_stars_invoice_data_returns_stars_invoice():
    mock_http = AsyncMock()
    mock_http.get.return_value = {
        "title": "BeatVault",
        "description": "MTProto proxy",
        "stars_price": 60,
    }
    client = PaymentsClient(_http=mock_http)
    result = await client.get_stars_invoice_data()

    assert isinstance(result, StarsInvoiceData)
    assert result.currency == "XTR"
    assert result.provider_token == ""
    assert result.prices[0].amount == 60


async def test_record_purchase_calls_correct_endpoint():
    mock_http = AsyncMock()
    mock_http.post.return_value = {}
    client = PaymentsClient(_http=mock_http)

    await client.record_purchase(
        telegram_id=123,
        charge_id="charge_abc",
        provider="yukassa",
    )

    mock_http.post.assert_called_once_with(
        path="/api/v1/payments/buy/",
        telegram_id="123",
        data={"username": "123", "charge_id": "charge_abc", "provider": "yukassa"},
    )


def test_get_payments_client_returns_instance():
    assert isinstance(get_payments_client(), PaymentsClient)
```

- [ ] **Step 4: Run tests — confirm they fail**

```bash
cd bot && uv run pytest tests/domains/payments/test_client.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 5: Implement payments/client.py**

Create `bot/src/domains/payments/client.py`:

```python
from __future__ import annotations

import json
from copy import copy
from dataclasses import asdict, dataclass, field
from typing import final

from aiogram.types import LabeledPrice

from core import config
from core.backend_client import BackendClient
from core.handle_error import log_service_error


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class InvoiceData:
    title: str
    description: str
    currency: str
    provider_data: str
    send_email_to_provider: bool
    need_email: bool
    prices: list
    provider_token: str

    def asdict(self) -> dict:
        return asdict(self)


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class StarsInvoiceData:
    title: str
    description: str
    prices: list
    currency: str = "XTR"
    provider_token: str = ""


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class PaymentsClient:
    _http: BackendClient = field(default_factory=BackendClient)

    async def get_invoice_data(self) -> InvoiceData:
        raw = copy(await self._http.get(path="/api/v1/payments/"))
        prices = [LabeledPrice(label=raw.get("title"), amount=raw.pop("price"))]
        provider_data = json.dumps(raw.pop("provider_data"))
        raw.pop("stars_price", None)
        return InvoiceData(
            **raw,
            provider_data=provider_data,
            prices=prices,
            provider_token=config.PROVIDER_TOKEN,
        )

    async def get_stars_invoice_data(self) -> StarsInvoiceData:
        raw = await self._http.get(path="/api/v1/payments/")
        prices = [LabeledPrice(label=raw["title"], amount=raw["stars_price"])]
        return StarsInvoiceData(
            title=raw["title"],
            description=raw["description"],
            prices=prices,
        )

    @log_service_error
    async def record_purchase(
        self, *, telegram_id: int, charge_id: str, provider: str
    ) -> None:
        await self._http.post(
            path="/api/v1/payments/buy/",
            telegram_id=str(telegram_id),
            data={
                "username": str(telegram_id),
                "charge_id": charge_id,
                "provider": provider,
            },
        )


def get_payments_client() -> PaymentsClient:
    return PaymentsClient()
```

- [ ] **Step 6: Run tests — confirm they pass**

```bash
cd bot && uv run pytest tests/domains/payments/test_client.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Create payments/handlers.py**

```python
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    Message,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import bot
from domains.payments.client import get_payments_client
from domains.payments.messages import PAYMENT_ERROR_TEXT, PAYMENT_SELECTION_TEXT

router = Router()


@router.callback_query(F.data == "boost_paid")
async def process_boost_paid(callback: CallbackQuery) -> None:
    await callback.answer()
    keyboard = InlineKeyboardBuilder(
        markup=[
            [InlineKeyboardButton(text="💳 ЮKassa — 79 ₽", callback_data="pay_yukassa")],
            [InlineKeyboardButton(text="⭐ Telegram Stars — 60 ★", callback_data="pay_stars")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")],
        ],
    )
    await callback.message.edit_text(
        text=PAYMENT_SELECTION_TEXT,
        parse_mode="HTML",
        reply_markup=keyboard.adjust(1).as_markup(),
    )


@router.callback_query(F.data == "pay_yukassa")
async def process_pay_yukassa(callback: CallbackQuery) -> None:
    await callback.answer()
    client = get_payments_client()
    response = await client.get_invoice_data()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        start_parameter="payment",
        payload="payment",
        **response.asdict(),
    )


@router.callback_query(F.data == "pay_stars")
async def process_pay_stars(callback: CallbackQuery) -> None:
    await callback.answer()
    client = get_payments_client()
    response = await client.get_stars_invoice_data()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=response.title,
        description=response.description,
        start_parameter="payment_stars",
        payload="payment_stars",
        currency=response.currency,
        prices=response.prices,
        provider_token=response.provider_token,
    )


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery) -> None:
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message) -> None:
    if message.successful_payment.currency == "XTR":
        charge_id = message.successful_payment.telegram_payment_charge_id
        provider = "stars"
    else:
        charge_id = message.successful_payment.provider_payment_charge_id
        provider = "yukassa"

    try:
        client = get_payments_client()
        await client.record_purchase(
            telegram_id=message.from_user.id,
            charge_id=charge_id,
            provider=provider,
        )
    except Exception:
        await message.answer(PAYMENT_ERROR_TEXT)
```

- [ ] **Step 8: Commit**

```bash
git add bot/src/domains/payments/ bot/tests/domains/payments/
git commit -m "feat(bot): add payments domain with client, handlers, messages"
```

---

## Task 6: referrals Domain

**Files:**
- Create: `bot/src/domains/referrals/__init__.py`, `bot/src/domains/referrals/messages.py`
- Create: `bot/src/domains/referrals/client.py`, `bot/src/domains/referrals/handlers.py`
- Create: `bot/tests/domains/referrals/__init__.py`, `bot/tests/domains/referrals/test_client.py`

- [ ] **Step 1: Create packages**

Create `bot/src/domains/referrals/__init__.py` — empty.
Create `bot/tests/domains/referrals/__init__.py` — empty.

- [ ] **Step 2: Create referrals/messages.py**

```python
from __future__ import annotations

REFERRAL_CABINET = """
<b>⚡️Твой реферальный кабинет </b> 

• Общее количество инвайтов: <b>{total_referrals_count}</b>
• Активированные инвайты: <b>{active_referrals_count}</b>

🔗 Как только количество активированных инвайтов станет равно <b>5</b>, ты сможешь получить бесплатную ссылку <b>сроком действия 2 недели!</b>

👇 <b>Поделиться ссылкой</b>
"""

# Same template as free_trial — duplicated here to avoid cross-domain import
KEY_GENERATED_TEXT = """
🎉 <b>Твой персональный ключ готов!</b>

🔑 Ключ находится в кнопке, прикрепленной к этому сообщению.

📝 <b>Как активировать:</b>
1. Нажми на ссылку в кнопке ниже
2. Нажми «подключить»

✅ <b>Готово!</b> Telegram теперь работает быстрее

⏳ Сссылка действительна до: <b>{expired_date}</b>

<i>🤝 Чтобы быть в курсе всех новостей, пожалуйста, подпишись на наш канал — @mtproto_keys</i>
"""
```

- [ ] **Step 3: Write failing tests for ReferralsClient**

Create `bot/tests/domains/referrals/test_client.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock

from domains.referrals.client import (
    ReferralCabinet,
    ReferralLink,
    ReferralsClient,
    get_referrals_client,
)


async def test_get_cabinet_returns_cabinet():
    mock_http = AsyncMock()
    mock_http.post.return_value = {
        "total_referrals_count": 10,
        "active_referrals_count": 5,
        "referral_link": "https://t.me/bot?start=123",
        "link_activated_count": 3,
    }
    client = ReferralsClient(_http=mock_http)
    result = await client.get_cabinet(telegram_id="123")

    assert isinstance(result, ReferralCabinet)
    assert result.active_referrals_count == 5
    assert result.referral_link == "https://t.me/bot?start=123"
    mock_http.post.assert_called_once_with(
        path="/api/v1/users/referral/cabinet/",
        telegram_id="123",
        data={"username": "123"},
    )


async def test_get_referral_link_returns_link():
    mock_http = AsyncMock()
    mock_http.post.return_value = {
        "link": "https://t.me/proxy?server=1.2.3.4",
        "expired_date": "2026-07-11",
    }
    client = ReferralsClient(_http=mock_http)
    result = await client.get_referral_link(telegram_id="123")

    assert isinstance(result, ReferralLink)
    assert result.link == "https://t.me/proxy?server=1.2.3.4"


def test_get_referrals_client_returns_instance():
    assert isinstance(get_referrals_client(), ReferralsClient)
```

- [ ] **Step 4: Run tests — confirm they fail**

```bash
cd bot && uv run pytest tests/domains/referrals/test_client.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 5: Implement referrals/client.py**

Create `bot/src/domains/referrals/client.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import final

from core.backend_client import BackendClient
from core.handle_error import log_service_error


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReferralCabinet:
    total_referrals_count: int | None
    active_referrals_count: int | None
    referral_link: str | None
    link_activated_count: int | None


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReferralLink:
    link: str
    expired_date: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReferralsClient:
    _http: BackendClient = field(default_factory=BackendClient)

    @log_service_error
    async def get_cabinet(self, *, telegram_id: str) -> ReferralCabinet:
        result = await self._http.post(
            path="/api/v1/users/referral/cabinet/",
            telegram_id=telegram_id,
            data={"username": telegram_id},
        )
        return ReferralCabinet(**result)

    @log_service_error
    async def get_referral_link(self, *, telegram_id: str) -> ReferralLink:
        result = await self._http.post(
            path="/api/v1/users/referral/link/",
            telegram_id=telegram_id,
            data={"username": telegram_id},
        )
        return ReferralLink(**result)


def get_referrals_client() -> ReferralsClient:
    return ReferralsClient()
```

- [ ] **Step 6: Run tests — confirm they pass**

```bash
cd bot && uv run pytest tests/domains/referrals/test_client.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Create referrals/handlers.py**

```python
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from domains.referrals.client import get_referrals_client
from domains.referrals.messages import KEY_GENERATED_TEXT, REFERRAL_CABINET

router = Router()


@router.callback_query(F.data == "referral")
async def process_referral(callback: CallbackQuery) -> None:
    await callback.answer()
    client = get_referrals_client()
    response = await client.get_cabinet(telegram_id=str(callback.message.chat.id))

    keyboard: list = []
    if response.active_referrals_count >= 5:
        keyboard.append(
            [InlineKeyboardButton(text="🎁 Получить бесплатную ссылку", callback_data="get-referral-link")]
        )
    keyboard.append(
        [InlineKeyboardButton(
            text="🔗 Поделиться ссылкой",
            switch_inline_query=f"Привет! Переходи по моей реферальной ссылке: {response.referral_link}",
        )]
    )
    keyboard.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")]
    )

    await callback.message.edit_text(
        text=REFERRAL_CABINET.format(
            total_referrals_count=response.total_referrals_count,
            active_referrals_count=response.active_referrals_count,
            referral_link=response.referral_link,
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


@router.callback_query(F.data == "get-referral-link")
async def process_referral_link(callback: CallbackQuery) -> None:
    await callback.answer()
    client = get_referrals_client()
    response = await client.get_referral_link(telegram_id=str(callback.message.chat.id))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇳🇱 Подключиться", url=response.link)]
        ]
    )
    await callback.message.answer(
        text=KEY_GENERATED_TEXT.format(expired_date=response.expired_date),
        parse_mode="HTML",
        reply_markup=keyboard,
    )
```

- [ ] **Step 8: Commit**

```bash
git add bot/src/domains/referrals/ bot/tests/domains/referrals/
git commit -m "feat(bot): add referrals domain with client, handlers, messages"
```

---

## Task 7: links Domain

**Files:**
- Create: `bot/src/domains/links/__init__.py`, `bot/src/domains/links/messages.py`
- Create: `bot/src/domains/links/client.py`, `bot/src/domains/links/handlers.py`
- Create: `bot/tests/domains/links/__init__.py`, `bot/tests/domains/links/test_client.py`

- [ ] **Step 1: Create packages**

Create `bot/src/domains/links/__init__.py` — empty.
Create `bot/tests/domains/links/__init__.py` — empty.

- [ ] **Step 2: Create links/messages.py**

```python
from __future__ import annotations

KEY_UPDATED_TEXT = """
<b>✅ Ссылка успешно обновлена!</b>
 
• ⚠️ Не забудь <b>удалить старую ссылку</b>, чтобы не запутаться! Она больше <b>НЕ будет работать</b>.
• ⚡️ Ссылка действительна до: <b>{expired_date}</b>.
• 📝 Не забудь подписаться на наш канал — там все новости: @mtproto_keys

<b>👇 Новая ссылка!</b>
"""
```

- [ ] **Step 3: Write failing tests for LinksClient**

Create `bot/tests/domains/links/test_client.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock

from domains.links.client import LinksClient, UpdatedLink, get_links_client


async def test_update_returns_updated_link():
    mock_http = AsyncMock()
    mock_http.post.return_value = {
        "link": "https://t.me/proxy?server=1.2.3.4",
        "expired_date": "2026-07-11",
    }
    client = LinksClient(_http=mock_http)
    result = await client.update(telegram_id="123")

    assert isinstance(result, UpdatedLink)
    assert result.link == "https://t.me/proxy?server=1.2.3.4"
    assert result.expired_date == "2026-07-11"
    mock_http.post.assert_called_once_with(
        path="/api/v1/users/update-link/",
        telegram_id="123",
        data={"username": "123"},
    )


def test_get_links_client_returns_instance():
    assert isinstance(get_links_client(), LinksClient)
```

- [ ] **Step 4: Run tests — confirm they fail**

```bash
cd bot && uv run pytest tests/domains/links/test_client.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 5: Implement links/client.py**

Create `bot/src/domains/links/client.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import final

from core.backend_client import BackendClient
from core.handle_error import log_service_error


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class UpdatedLink:
    link: str
    expired_date: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class LinksClient:
    _http: BackendClient = field(default_factory=BackendClient)

    @log_service_error
    async def update(self, *, telegram_id: str) -> UpdatedLink:
        result = await self._http.post(
            path="/api/v1/users/update-link/",
            telegram_id=telegram_id,
            data={"username": telegram_id},
        )
        return UpdatedLink(**result)


def get_links_client() -> LinksClient:
    return LinksClient()
```

- [ ] **Step 6: Run tests — confirm they pass**

```bash
cd bot && uv run pytest tests/domains/links/test_client.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Create links/handlers.py**

```python
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from domains.links.client import get_links_client
from domains.links.messages import KEY_UPDATED_TEXT

router = Router()


@router.callback_query(F.data == "update_link")
async def update_link(callback: CallbackQuery) -> None:
    await callback.answer()
    client = get_links_client()
    response = await client.update(telegram_id=str(callback.message.chat.id))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇳🇱 Подключиться", url=response.link)]
        ]
    )
    await callback.message.answer(
        text=KEY_UPDATED_TEXT.format(expired_date=response.expired_date),
        parse_mode="HTML",
        reply_markup=keyboard,
    )
```

- [ ] **Step 8: Commit**

```bash
git add bot/src/domains/links/ bot/tests/domains/links/
git commit -m "feat(bot): add links domain with client, handlers, messages"
```

---

## Task 8: Entry Point Wiring

**Files:**
- Create: `bot/src/router.py`, `bot/src/main.py`
- Modify: `bot/src/bot.py`

- [ ] **Step 1: Create router.py**

Create `bot/src/router.py`:

```python
from __future__ import annotations

from aiogram import Router

from domains.free_trial.handlers import router as free_trial_router
from domains.links.handlers import router as links_router
from domains.payments.handlers import router as payments_router
from domains.referrals.handlers import router as referrals_router

main_router = Router()
main_router.include_routers(
    free_trial_router,
    payments_router,
    referrals_router,
    links_router,
)
```

- [ ] **Step 2: Simplify bot.py**

Replace the entire contents of `bot/src/bot.py` with:

```python
from __future__ import annotations

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from core.config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
```

- [ ] **Step 3: Create main.py**

Create `bot/src/main.py`:

```python
from __future__ import annotations

import asyncio
import logging

from aiogram import Dispatcher

from bot import bot
from router import main_router

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    dp = Dispatcher()
    dp.include_router(main_router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Бот остановлен пользователем")
```

- [ ] **Step 4: Run all tests — confirm nothing broke**

```bash
cd bot && uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add bot/src/bot.py bot/src/router.py bot/src/main.py
git commit -m "refactor(bot): add router.py and main.py, simplify bot.py to Bot instance only"
```

---

## Task 9: Cleanup

**Delete old files, verify the bot starts.**

- [ ] **Step 1: Delete old flat files**

```bash
rm bot/src/handlers.py
rm bot/src/messages.py
rm bot/src/enums.py
rm bot/src/config.py
rm bot/src/exceptions.py
rm -rf bot/src/services/
```

- [ ] **Step 2: Run all tests — confirm nothing broke**

```bash
cd bot && uv run pytest -v
```

Expected: all tests still pass (they import from new paths only).

- [ ] **Step 3: Verify bot starts without import errors**

```bash
cd bot && PYTHONPATH=src uv run python -c "from main import main; print('OK')" 2>&1 | head -5
```

Expected: `OK` — no import errors.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "refactor(bot): remove old flat structure — handlers, messages, services, enums, config"
```
