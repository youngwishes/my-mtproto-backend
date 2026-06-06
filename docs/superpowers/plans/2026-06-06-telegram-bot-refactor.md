# Рефакторинг TelegramBot + приложение notifications — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **ВАЖНО:** Никогда не выполнять git-команды. Коммиты, пуши, ветки — пользователь делает сам.

**Goal:** Рефакторинг монолитного `TelegramBot` класса в три слоя: транспорт (`core/telegram/`), логирование ошибок (`core/telegram/error_logger.py`), пользовательские уведомления (приложение `notifications/` с БД-шаблонами и рассылками из Django Admin).

**Architecture:** `TelegramBot` (stateless class с classmethods) разделяется на функции транспорта и error-логирования в `apps/core/telegram/`. Пользовательские уведомления мигрируют в новое приложение `apps/notifications/` с моделями `NotificationTemplate` и `Mailing`, управляемыми из Django Admin. Существующие захардкоженные сообщения создаются data-миграцией.

**Tech Stack:** Django, Celery, pyTelegramBotAPI, factory_boy

**Spec:** `docs/superpowers/specs/2026-06-06-telegram-bot-refactor-design.md`

---

### File Map

**Create:**
- `src/apps/core/telegram/__init__.py`
- `src/apps/core/telegram/transport.py`
- `src/apps/core/telegram/error_logger.py`
- `src/apps/notifications/__init__.py`
- `src/apps/notifications/apps.py`
- `src/apps/notifications/models.py`
- `src/apps/notifications/enums.py`
- `src/apps/notifications/selectors.py`
- `src/apps/notifications/resolvers.py`
- `src/apps/notifications/admin.py`
- `src/apps/notifications/tasks.py`
- `src/apps/notifications/services/__init__.py`
- `src/apps/notifications/services/send_notification_service.py`
- `src/apps/notifications/services/send_mailing_service.py`
- `src/apps/notifications/tests/__init__.py`
- `src/apps/notifications/tests/factories.py`
- `src/apps/notifications/tests/test_models.py`
- `src/apps/notifications/tests/test_selectors.py`
- `src/apps/notifications/tests/test_resolvers.py`
- `src/apps/notifications/tests/test_send_notification_service.py`
- `src/apps/notifications/tests/test_send_mailing_service.py`
- `src/apps/core/tests/__init__.py`
- `src/apps/core/tests/test_transport.py`
- `src/apps/core/tests/test_error_logger.py`
- `src/apps/notifications/migrations/0002_seed_templates.py`

**Modify:**
- `src/apps/core/service.py:5,45,57-58` — обновить импорты, заменить TelegramBot вызовы
- `src/config/settings/base.py:44-56` — добавить `apps.notifications` в INSTALLED_APPS
- `src/apps/vds/tasks.py:9,31,64,68,100,107,135,140,169,200,240,272` — заменить TelegramBot/bot вызовы
- `src/apps/users/tasks.py:7,21,23,48` — заменить TelegramBot вызовы
- `src/apps/payments/services/notify_payment_service.py:6,19` — заменить TelegramBot вызовы
- `src/apps/users/api/v1/views/first_free_link_view.py:6,22,36` — убрать notify_bad_request
- `src/apps/payments/tests/test_notify_payment_service.py:20-21` — обновить mock path

**Delete:**
- `src/apps/core/bot.py`

---

### Task 1: Создание `apps/core/telegram/transport.py`

**Files:**
- Create: `src/apps/core/telegram/__init__.py`
- Create: `src/apps/core/telegram/transport.py`
- Create: `src/apps/core/tests/__init__.py`
- Create: `src/apps/core/tests/test_transport.py`

- [ ] **Step 1: Написать тесты для transport**

```python
# src/apps/core/tests/__init__.py
# (пустой файл)
```

```python
# src/apps/core/tests/test_transport.py
from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings
from telebot.types import InlineKeyboardMarkup


class TestSend(TestCase):
    @mock.patch("apps.core.telegram.transport.bot")
    def test_send_calls_bot_send_message_with_defaults(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import send

        send(chat_id=123, text="hello")

        mock_bot.send_message.assert_called_once_with(
            chat_id=123,
            text="hello",
            parse_mode="HTML",
            reply_markup=None,
            timeout=None,
        )

    @mock.patch("apps.core.telegram.transport.bot")
    def test_send_passes_markup_and_timeout(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import send

        markup = InlineKeyboardMarkup()
        send(chat_id=456, text="test", markup=markup, timeout=10)

        mock_bot.send_message.assert_called_once_with(
            chat_id=456,
            text="test",
            parse_mode="HTML",
            reply_markup=markup,
            timeout=10,
        )

    @mock.patch("apps.core.telegram.transport.bot")
    def test_send_custom_parse_mode(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import send

        send(chat_id=789, text="**bold**", parse_mode="Markdown")

        mock_bot.send_message.assert_called_once_with(
            chat_id=789,
            text="**bold**",
            parse_mode="Markdown",
            reply_markup=None,
            timeout=None,
        )


class TestIsChannelMember(TestCase):
    @mock.patch("apps.core.telegram.transport.bot")
    @override_settings(TELEGRAM_CHANNEL_ID="-100123")
    def test_returns_true_for_member(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import is_channel_member

        mock_member = mock.Mock()
        mock_member.status = "member"
        mock_bot.get_chat_member.return_value = mock_member

        result = is_channel_member(telegram_id=111)

        self.assertTrue(result)
        mock_bot.get_chat_member.assert_called_once_with(
            chat_id="-100123", user_id=111,
        )

    @mock.patch("apps.core.telegram.transport.bot")
    @override_settings(TELEGRAM_CHANNEL_ID="-100123")
    def test_returns_true_for_administrator(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import is_channel_member

        mock_member = mock.Mock()
        mock_member.status = "administrator"
        mock_bot.get_chat_member.return_value = mock_member

        self.assertTrue(is_channel_member(telegram_id=222))

    @mock.patch("apps.core.telegram.transport.bot")
    @override_settings(TELEGRAM_CHANNEL_ID="-100123")
    def test_returns_false_for_left(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import is_channel_member

        mock_member = mock.Mock()
        mock_member.status = "left"
        mock_bot.get_chat_member.return_value = mock_member

        self.assertFalse(is_channel_member(telegram_id=333))
```

- [ ] **Step 2: Запустить тесты, убедиться что падают**

Run: `make test ARGS="apps.core.tests.test_transport"`
Expected: FAIL — модуль `apps.core.telegram.transport` не существует

- [ ] **Step 3: Реализовать transport.py**

```python
# src/apps/core/telegram/__init__.py
from apps.core.telegram.transport import is_channel_member, send

__all__ = ["send", "is_channel_member"]
```

```python
# src/apps/core/telegram/transport.py
from __future__ import annotations

from django.conf import settings
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup


class _LazyBot:
    """Прокси, создающий TeleBot при первом обращении, а не при импорте модуля."""

    _instance: TeleBot | None = None

    def __getattr__(self, name: str):
        if self._instance is None:
            self._instance = TeleBot(token=settings.BOT_TOKEN)
        return getattr(self._instance, name)


bot = _LazyBot()


def send(
    chat_id: int,
    text: str,
    *,
    parse_mode: str = "HTML",
    markup: InlineKeyboardMarkup | None = None,
    timeout: int | None = None,
) -> None:
    bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
        reply_markup=markup,
        timeout=timeout,
    )


def is_channel_member(telegram_id: int) -> bool:
    member = bot.get_chat_member(
        chat_id=settings.TELEGRAM_CHANNEL_ID, user_id=telegram_id,
    )
    return member.status in ["member", "administrator", "creator"]
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `make test ARGS="apps.core.tests.test_transport"`
Expected: OK (6 tests)

---

### Task 2: Создание `apps/core/telegram/error_logger.py`

**Files:**
- Create: `src/apps/core/tests/test_error_logger.py`
- Modify: `src/apps/core/telegram/__init__.py`
- Create: `src/apps/core/telegram/error_logger.py`

- [ ] **Step 1: Написать тесты для error_logger**

```python
# src/apps/core/tests/test_error_logger.py
from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings

from apps.core.service import BaseInfraError, BaseServiceError


class TestLogInfraError(TestCase):
    @mock.patch("apps.core.telegram.error_logger.send")
    @override_settings(MY_TELEGRAM_ID=999, TELEGRAM_TIMEOUT=5)
    def test_sends_red_error_to_admin(self, mock_send: mock.Mock) -> None:
        from apps.core.telegram.error_logger import log_infra_error

        exc = BaseInfraError(telegram_id=123, message="VDS down")
        log_infra_error(exc)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        self.assertEqual(call_kwargs.kwargs["chat_id"], 999)
        self.assertIn("🔴", call_kwargs.kwargs["text"])
        self.assertIn("SERVER INTERNAL ERROR (500)", call_kwargs.kwargs["text"])
        self.assertIn("VDS down", call_kwargs.kwargs["text"])
        self.assertEqual(call_kwargs.kwargs["timeout"], 5)


class TestLogServiceError(TestCase):
    @mock.patch("apps.core.telegram.error_logger.send")
    @override_settings(MY_TELEGRAM_ID=999, TELEGRAM_TIMEOUT=5)
    def test_sends_yellow_error_to_admin(self, mock_send: mock.Mock) -> None:
        from apps.core.telegram.error_logger import log_service_error

        exc = BaseServiceError(telegram_id=456, message="Product not found")
        log_service_error(exc)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        self.assertEqual(call_kwargs.kwargs["chat_id"], 999)
        self.assertIn("🟡", call_kwargs.kwargs["text"])
        self.assertIn("SERVICE (400)", call_kwargs.kwargs["text"])
        self.assertIn("Product not found", call_kwargs.kwargs["text"])
```

- [ ] **Step 2: Запустить тесты, убедиться что падают**

Run: `make test ARGS="apps.core.tests.test_error_logger"`
Expected: FAIL — модуль `apps.core.telegram.error_logger` не существует

- [ ] **Step 3: Реализовать error_logger.py**

```python
# src/apps/core/telegram/error_logger.py
from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING

from django.conf import settings

from apps.core.telegram.transport import send

if TYPE_CHECKING:
    from apps.core.service import BaseInfraError, BaseServiceError


def _log_error(
    exc: BaseInfraError | BaseServiceError,
    *,
    emoji: str,
    error_type: str,
    attention_text: str,
) -> None:
    error_dict = exc.to_dict()
    pretty_error = json.dumps(error_dict, indent=2, ensure_ascii=False)
    escaped_error = html.escape(pretty_error)
    send(
        chat_id=settings.MY_TELEGRAM_ID,
        text=(
            f"{emoji} <b>(BACKEND) Системное оповещение</b>\n\n"
            f"🛡 <b>Тип ошибки:</b> {error_type}\n"
            f"📋 <b>Детали:</b>\n"
            f"<code>{escaped_error}</code>\n\n"
            f"⚙️ <i>{attention_text}</i>"
        ),
        timeout=settings.TELEGRAM_TIMEOUT,
    )


def log_infra_error(exc: BaseInfraError) -> None:
    _log_error(
        exc,
        emoji="🔴",
        error_type="SERVER INTERNAL ERROR (500)",
        attention_text="Требуется СРОЧНОЕ внимание команды",
    )


def log_service_error(exc: BaseServiceError) -> None:
    _log_error(
        exc,
        emoji="🟡",
        error_type="SERVICE (400)",
        attention_text="Возможно, требуется внимание команды",
    )
```

- [ ] **Step 4: Обновить `__init__.py`**

```python
# src/apps/core/telegram/__init__.py
from apps.core.telegram.error_logger import log_infra_error, log_service_error
from apps.core.telegram.transport import is_channel_member, send

__all__ = [
    "send",
    "is_channel_member",
    "log_infra_error",
    "log_service_error",
]
```

- [ ] **Step 5: Запустить тесты, убедиться что проходят**

Run: `make test ARGS="apps.core.tests.test_error_logger"`
Expected: OK (2 tests)

---

### Task 3: Обновление декораторов в `apps/core/service.py`

**Files:**
- Modify: `src/apps/core/service.py:5,39-48,51-61`

- [ ] **Step 1: Обновить service.py**

Заменить содержимое файла `src/apps/core/service.py`:

```python
# src/apps/core/service.py
import logging
from dataclasses import asdict, dataclass
from functools import wraps
from typing import Any, Callable, Protocol

from apps.core.telegram.error_logger import (
    log_infra_error as _log_infra_error,
    log_service_error as _log_service_error,
)

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


@dataclass(kw_only=True, frozen=True, slots=True)
class BaseServiceDTO:
    def asdict(self) -> dict:
        return asdict(self)


def log_service_error(__call__: Callable) -> Callable:
    @wraps(__call__)
    def wrapper(self, **kwargs) -> Any:
        try:
            return __call__(self, **kwargs)
        except BaseServiceError as service_error:
            _log_service_error(service_error)
            raise service_error

    return wrapper


def log_infra_error(__call__: Callable) -> Callable:
    @wraps(__call__)
    def wrapper(self, **kwargs) -> Any:
        try:
            return __call__(self, **kwargs)
        except BaseInfraError as infra_error:
            _log_infra_error(infra_error)
            raise infra_error

    return wrapper
```

**Важно:** Декоратор `log_infra_error` больше не вызывает `send_sorry`. Уведомление пользователя ("sorry") будет добавлено после создания приложения `notifications` (Task 9, step по обновлению декоратора).

- [ ] **Step 2: Запустить все тесты, убедиться что существующие тесты проходят**

Run: `make test`
Expected: OK — все существующие тесты должны пройти, т.к. `apps/core/bot.py` ещё не удалён и старые импорты в других файлах работают.

---

### Task 4: Приложение `notifications` — модели и enums

**Files:**
- Create: `src/apps/notifications/__init__.py`
- Create: `src/apps/notifications/apps.py`
- Create: `src/apps/notifications/enums.py`
- Create: `src/apps/notifications/models.py`
- Create: `src/apps/notifications/tests/__init__.py`
- Create: `src/apps/notifications/tests/test_models.py`
- Modify: `src/config/settings/base.py:44-56`

- [ ] **Step 1: Написать тесты для моделей**

```python
# src/apps/notifications/tests/__init__.py
# (пустой файл)
```

```python
# src/apps/notifications/tests/test_models.py
from __future__ import annotations

from django.test import TestCase
from django.utils import timezone

from apps.notifications.enums import MailingStatus
from apps.notifications.tests.factories import MailingFactory, NotificationTemplateFactory


class TestNotificationTemplateRender(TestCase):
    def test_render_text_without_variables(self) -> None:
        template = NotificationTemplateFactory(
            text="Привет! Это тест.",
            button_text="",
            button_url="",
        )

        result = template.render()

        self.assertEqual(result.text, "Привет! Это тест.")
        self.assertIsNone(result.markup)

    def test_render_text_with_variables(self) -> None:
        template = NotificationTemplateFactory(
            text="Привет, твоя ссылка: {link}",
            button_text="",
            button_url="",
        )

        result = template.render(context={"link": "https://example.com"})

        self.assertEqual(result.text, "Привет, твоя ссылка: https://example.com")

    def test_render_with_button(self) -> None:
        template = NotificationTemplateFactory(
            text="Нажми кнопку",
            button_text="Подключиться",
            button_url="https://t.me/proxy?server={link}",
        )

        result = template.render(context={"link": "abc123"})

        self.assertEqual(result.text, "Нажми кнопку")
        self.assertIsNotNone(result.markup)
        button = result.markup.keyboard[0][0]
        self.assertEqual(button.text, "Подключиться")
        self.assertEqual(button.url, "https://t.me/proxy?server=abc123")

    def test_render_without_context_returns_raw_text(self) -> None:
        template = NotificationTemplateFactory(
            text="Текст без переменных",
            button_text="",
            button_url="",
        )

        result = template.render()

        self.assertEqual(result.text, "Текст без переменных")


class TestMailingLifecycle(TestCase):
    def test_mark_as_sending(self) -> None:
        mailing = MailingFactory(status=MailingStatus.DRAFT)

        mailing.mark_as_sending()
        mailing.refresh_from_db()

        self.assertEqual(mailing.status, MailingStatus.SENDING)

    def test_mark_as_completed(self) -> None:
        mailing = MailingFactory(status=MailingStatus.SENDING)

        mailing.mark_as_completed()
        mailing.refresh_from_db()

        self.assertEqual(mailing.status, MailingStatus.COMPLETED)
        self.assertIsNotNone(mailing.sent_at)
```

- [ ] **Step 2: Создать фабрики**

```python
# src/apps/notifications/tests/factories.py
from __future__ import annotations

import factory

from apps.notifications.enums import ContextResolverType, FilterType, MailingStatus
from apps.notifications.models import Mailing, NotificationTemplate


class NotificationTemplateFactory(factory.django.DjangoModelFactory):
    slug = factory.Sequence(lambda n: f"template-{n}")
    title = factory.Sequence(lambda n: f"Template {n}")
    text = "Default text"
    button_text = ""
    button_url = ""

    class Meta:
        model = NotificationTemplate


class MailingFactory(factory.django.DjangoModelFactory):
    template = factory.SubFactory(NotificationTemplateFactory)
    filter_type = FilterType.ALL_ACTIVE
    filter_params = factory.LazyFunction(dict)
    context = factory.LazyFunction(dict)
    context_resolver = ContextResolverType.NONE
    status = MailingStatus.DRAFT

    class Meta:
        model = Mailing
```

- [ ] **Step 3: Запустить тесты, убедиться что падают**

Run: `make test ARGS="apps.notifications.tests.test_models"`
Expected: FAIL — приложение `notifications` не существует

- [ ] **Step 4: Создать приложение**

```python
# src/apps/notifications/__init__.py
# (пустой файл)
```

```python
# src/apps/notifications/apps.py
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    verbose_name = "Уведомления"
```

```python
# src/apps/notifications/enums.py
from __future__ import annotations

import enum


class MailingStatus(enum.IntEnum):
    DRAFT = 1
    SENDING = 2
    COMPLETED = 3
    FAILED = 4

    @classmethod
    def choices(cls) -> list[tuple[int, str]]:
        return [
            (cls.DRAFT, "Черновик"),
            (cls.SENDING, "Отправляется"),
            (cls.COMPLETED, "Завершена"),
            (cls.FAILED, "Ошибка"),
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
```

```python
# src/apps/notifications/models.py
from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.core.models import BaseDjangoModel
from apps.notifications.enums import ContextResolverType, FilterType, MailingStatus


class NotificationTemplate(BaseDjangoModel):
    slug = models.SlugField("Идентификатор", max_length=64, unique=True)
    title = models.CharField("Название", max_length=255)
    text = models.TextField("Текст сообщения (HTML, поддерживает {переменные})")
    button_text = models.CharField(
        "Текст кнопки", max_length=128, blank=True, default="",
    )
    button_url = models.CharField(
        "URL кнопки (поддерживает {переменные})", max_length=512, blank=True, default="",
    )

    class Meta:
        verbose_name = "Шаблон уведомления"
        verbose_name_plural = "Шаблоны уведомлений"

    def __str__(self) -> str:
        return self.title

    def render(self, context: dict | None = None) -> RenderedMessage:
        ctx = context or {}
        text = self.text.format(**ctx)
        markup = None
        if self.button_text and self.button_url:
            from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

            markup = InlineKeyboardMarkup(
                keyboard=[
                    [
                        InlineKeyboardButton(
                            text=self.button_text,
                            url=self.button_url.format(**ctx),
                        )
                    ]
                ]
            )
        return RenderedMessage(text=text, markup=markup)


class RenderedMessage:
    """Результат рендеринга шаблона."""

    __slots__ = ("text", "markup")

    def __init__(self, text: str, markup=None) -> None:
        self.text = text
        self.markup = markup


class Mailing(BaseDjangoModel):
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.CASCADE,
        verbose_name="Шаблон",
    )
    filter_type = models.IntegerField(
        "Фильтр получателей",
        choices=FilterType.choices(),
    )
    filter_params = models.JSONField(
        "Параметры фильтра", default=dict, blank=True,
    )
    context = models.JSONField(
        "Статический контекст для шаблона", default=dict, blank=True,
    )
    context_resolver = models.IntegerField(
        "Персональный контекст",
        choices=ContextResolverType.choices(),
        default=ContextResolverType.NONE,
    )
    status = models.IntegerField(
        "Статус",
        choices=MailingStatus.choices(),
        default=MailingStatus.DRAFT,
    )
    sent_at = models.DateTimeField("Отправлена", null=True, blank=True)

    class Meta:
        verbose_name = "Рассылка"
        verbose_name_plural = "Рассылки"

    def __str__(self) -> str:
        return f"{self.template.title} — {self.get_status_display()}"

    def mark_as_sending(self) -> None:
        self.status = MailingStatus.SENDING
        self.save(update_fields=["status"])

    def mark_as_completed(self) -> None:
        self.status = MailingStatus.COMPLETED
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])
```

- [ ] **Step 5: Зарегистрировать приложение в INSTALLED_APPS**

В файле `src/config/settings/base.py` добавить `"apps.notifications"` в `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.users",
    "apps.vds",
    "apps.music",
    "apps.payments",
    "apps.notifications",
    "rest_framework",
]
```

- [ ] **Step 6: Создать и применить миграции**

Run: `cd src && python manage.py makemigrations notifications`
Expected: создаётся `0001_initial.py`

Run: `cd src && python manage.py migrate`
Expected: миграция применена

- [ ] **Step 7: Запустить тесты моделей**

Run: `make test ARGS="apps.notifications.tests.test_models"`
Expected: OK (6 tests)

---

### Task 5: Data-миграция существующих шаблонов

**Files:**
- Create: `src/apps/notifications/migrations/0002_seed_templates.py`

- [ ] **Step 1: Создать data-миграцию**

```python
# src/apps/notifications/migrations/0002_seed_templates.py
from __future__ import annotations

from django.db import migrations


TEMPLATES = [
    {
        "slug": "invite_to_channel",
        "title": "Приглашение на канал",
        "text": (
            "👋 <b>Привет!</b>\n\n"
            "⚡️ Чтобы поддерживать стабильность работы прокси, на наших серверах каждую неделю "
            "проводятся технические работы. <b>Мы заранее предупреждаем об этом в нашем телеграм канале — @mtproto_keys.</b>\n\n"
            "📢 Также там появляется информация о новых функциях в нашем боте.\n\n"
            "👇 Пожалуйста, чтобы ничего не пропускать — подпишись, <b>я там пишу редко, но по делу.</b>"
        ),
        "button_text": "👉 Перейти на канал",
        "button_url": "https://t.me/mtproto_keys/",
    },
    {
        "slug": "before_expiry_1day",
        "title": "Напоминание за 1 день до истечения",
        "text": (
            "⚠️ <b>До окончания остался 1 день</b>\n\n"
            "Привет! Наверное, ты заметил, что у нашего прокси <b>нет рекламы, нет спонсоров</b> — и это так.\n\n"
            "Мы ничего не продаём, не встраиваем баннеры и не передаём твои данные. Просто <b>честно поддерживаем сервис в рабочем состоянии.</b>\n\n"
            "Но серверы и обслуживание — это наши <b>реальные расходы.</b> Если тебе удобно пользоваться прокси и хочется его поддержать, можешь <b>продлить доступ на месяц всего за 79 ₽</b>.\n\n"
            "Это поможет нам оставаться <b>независимыми</b> и дальше держать <b>стабильную</b> работу.\n\n"
            "👇 <b>Поддежать проект</b>"
        ),
        "button_text": "⚡️ ПРОДЛИТЬ ЗА 79 ₽",
        "button_url": "",
    },
    {
        "slug": "before_expiry_1hour",
        "title": "Напоминание за 1 час до истечения",
        "text": (
            "⚠️ <b>Ссылка истечет ровно через 1 час!</b>\n\n"
            "Привет! Наверное, ты заметил, что у нашего прокси <b>нет рекламы, нет спонсоров</b> — и это так.\n\n"
            "Мы ничего не продаём, не встраиваем баннеры и не передаём твои данные. Просто <b>честно поддерживаем сервис в рабочем состоянии.</b>\n\n"
            "Но серверы и обслуживание — это наши <b>реальные расходы.</b> Если тебе удобно пользоваться прокси и хочется его поддержать, можешь <b>продлить доступ на месяц всего за 79 ₽</b>.\n\n"
            "Это поможет нам оставаться <b>независимыми</b> и дальше держать <b>стабильную</b> работу.\n\n"
            "👇 <b>Поддежать проект</b>"
        ),
        "button_text": "⚡️ ПРОДЛИТЬ ЗА 79 ₽",
        "button_url": "",
    },
    {
        "slug": "link_deactivated",
        "title": "Ссылка деактивирована",
        "text": (
            "👋 Привет!\n\n"
            "Срок действия твоей ссылки подошел к концу, и теперь Telegram может работать медленнее.\n\n"
            "<b>Но есть отличная новость:</b> ты можешь легко вернуть скорость обратно!\n\n"
            "👉 <b>Для этого нажми на кнопку ниже:</b>"
        ),
        "button_text": "🚀 ВЕРНУТЬ СКОРОСТЬ (79 RUB)",
        "button_url": "",
    },
    {
        "slug": "proxy_purchased",
        "title": "Покупка прокси",
        "text": (
            "🎉 <b>Спасибо за покупку!</b>\n\n"
            "✨ Ваш VPN-ключ готов к использованию.\n"
            "👉 Нажмите кнопку <b>«🇳🇱 Подключиться»</b> ниже.\n\n"
            "⏳ <b>Важно:</b> ссылка действует <b>30 дней</b> с момента покупки.\n"
            "🗓 После этого срока доступ потребуется продлить."
        ),
        "button_text": "🇳🇱 Подключиться",
        "button_url": "{link}",
    },
    {
        "slug": "proxy_link_with_message",
        "title": "Прокси-ссылка с текстом",
        "text": "{text}",
        "button_text": "🇳🇱 Подключиться",
        "button_url": "{link}",
    },
    {
        "slug": "sorry_server_error",
        "title": "Извинение за серверную ошибку",
        "text": (
            "✨ <b>Уважаемый клиент</b>\n\n"
            "К сожалению, в данный момент наши серверы испытывают "
            "<b>повышенные нагрузки</b>. Наши инженеры уже занимаются "
            "решением вопроса, чтобы восстановить работу в кратчайшие сроки.\n\n"
            "Мы ценим ваше терпение и понимание. Если вы только что приобрели"
            " ключ, чтобы не заставлять вас ждать, "
            "пожалуйста, <b>направьте это сообщение в поддержку</b> — вам "
            "оперативно предоставят доступ в ручном режиме.\n\n"
            "📩 <b>Поддержка:</b> @mtproto_keys\n\n"
            "<i>С уважением, команда сервиса</i>"
        ),
        "button_text": "",
        "button_url": "",
    },
]


def forwards(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    for data in TEMPLATES:
        NotificationTemplate.objects.create(**data)


def backwards(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    slugs = [t["slug"] for t in TEMPLATES]
    NotificationTemplate.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
```

**Замечание:** Шаблоны `before_expiry_1day`, `before_expiry_1hour`, `link_deactivated` имеют `button_url=""` — их кнопки в оригинале используют `callback_data` (обработчик на стороне бота), а не URL. Кнопки для этих шаблонов — callback, что выходит за рамки модели `NotificationTemplate` (она поддерживает только URL-кнопки). Для этих шаблонов кнопка не будет рендериться — текст отправится без кнопки. Если callback-кнопки нужны, это отдельная доработка модели.

- [ ] **Step 2: Применить миграцию**

Run: `cd src && python manage.py migrate notifications`
Expected: `0002_seed_templates` applied

- [ ] **Step 3: Проверить что шаблоны созданы**

Run: `cd src && python manage.py shell -c "from apps.notifications.models import NotificationTemplate; print(NotificationTemplate.objects.count())"`
Expected: `7`

---

### Task 6: Селекторы и резолверы

**Files:**
- Create: `src/apps/notifications/selectors.py`
- Create: `src/apps/notifications/resolvers.py`
- Create: `src/apps/notifications/tests/test_selectors.py`
- Create: `src/apps/notifications/tests/test_resolvers.py`

- [ ] **Step 1: Написать тесты для селекторов**

```python
# src/apps/notifications/tests/test_selectors.py
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.notifications.enums import FilterType
from apps.notifications.selectors import get_mailing_by_id, get_template, get_users_by_filter
from apps.notifications.tests.factories import MailingFactory, NotificationTemplateFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestGetTemplate(TestCase):
    def test_returns_active_template_by_slug(self) -> None:
        template = NotificationTemplateFactory(slug="test-slug")

        result = get_template(slug="test-slug")

        self.assertEqual(result.pk, template.pk)

    def test_raises_for_inactive_template(self) -> None:
        NotificationTemplateFactory(slug="inactive", is_active=False)

        from apps.notifications.models import NotificationTemplate

        with self.assertRaises(NotificationTemplate.DoesNotExist):
            get_template(slug="inactive")

    def test_raises_for_nonexistent_slug(self) -> None:
        from apps.notifications.models import NotificationTemplate

        with self.assertRaises(NotificationTemplate.DoesNotExist):
            get_template(slug="nonexistent")


class TestGetMailingById(TestCase):
    def test_returns_mailing_with_template(self) -> None:
        mailing = MailingFactory()

        result = get_mailing_by_id(mailing_id=mailing.pk)

        self.assertEqual(result.pk, mailing.pk)
        self.assertEqual(result.template.pk, mailing.template.pk)


class TestGetUsersByFilter(TestCase):
    def test_all_active_returns_active_users(self) -> None:
        user1 = SystemUserFactory(is_active=True)
        user2 = SystemUserFactory(is_active=True)
        SystemUserFactory(is_active=False)

        result = get_users_by_filter(
            filter_type=FilterType.ALL_ACTIVE, params={},
        )

        self.assertEqual(set(result.values_list("pk", flat=True)), {user1.pk, user2.pk})

    def test_expiring_soon_returns_users_with_expiring_keys(self) -> None:
        vds = VDSInstanceFactory()
        user_expiring = SystemUserFactory()
        user_safe = SystemUserFactory()

        MTPRotoKeyFactory(
            user=user_expiring,
            vds=vds,
            expired_date=timezone.now() + timedelta(hours=12),
            was_deleted=False,
        )
        MTPRotoKeyFactory(
            user=user_safe,
            vds=vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
        )

        result = get_users_by_filter(
            filter_type=FilterType.EXPIRING_SOON,
            params={"days_until_expiry": 1},
        )

        self.assertEqual(list(result.values_list("pk", flat=True)), [user_expiring.pk])
```

- [ ] **Step 2: Написать тесты для резолверов**

```python
# src/apps/notifications/tests/test_resolvers.py
from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.notifications.enums import ContextResolverType
from apps.notifications.resolvers import resolve_context
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestResolveContext(TestCase):
    def test_none_resolver_returns_empty_dict(self) -> None:
        user = SystemUserFactory()

        result = resolve_context(
            resolver_type=ContextResolverType.NONE, user=user,
        )

        self.assertEqual(result, {})

    def test_active_key_link_returns_link(self) -> None:
        user = SystemUserFactory()
        vds = VDSInstanceFactory()
        key = MTPRotoKeyFactory(
            user=user,
            vds=vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
        )

        result = resolve_context(
            resolver_type=ContextResolverType.ACTIVE_KEY_LINK, user=user,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["link"], key.get_proxy_link())

    def test_active_key_link_returns_none_when_no_key(self) -> None:
        user = SystemUserFactory()

        result = resolve_context(
            resolver_type=ContextResolverType.ACTIVE_KEY_LINK, user=user,
        )

        self.assertIsNone(result)
```

- [ ] **Step 3: Запустить тесты, убедиться что падают**

Run: `make test ARGS="apps.notifications.tests.test_selectors apps.notifications.tests.test_resolvers"`
Expected: FAIL — модули не существуют

- [ ] **Step 4: Реализовать селекторы**

```python
# src/apps/notifications/selectors.py
from __future__ import annotations

from django.db.models import QuerySet

from apps.notifications.enums import FilterType
from apps.notifications.models import Mailing, NotificationTemplate


def get_template(*, slug: str) -> NotificationTemplate:
    return NotificationTemplate.objects.active().get(slug=slug)


def get_mailing_by_id(*, mailing_id: int) -> Mailing:
    return Mailing.objects.select_related("template").get(id=mailing_id)


def get_users_by_filter(*, filter_type: int, params: dict) -> QuerySet:
    filters = {
        FilterType.ALL_ACTIVE: _all_active_users,
        FilterType.EXPIRING_SOON: _expiring_soon,
        FilterType.NOT_SUBSCRIBED: _not_subscribed,
    }
    return filters[filter_type](params)


def _all_active_users(params: dict) -> QuerySet:
    from apps.users.models import SystemUser

    return SystemUser.objects.filter(is_active=True)


def _expiring_soon(params: dict) -> QuerySet:
    from datetime import timedelta

    from django.utils.timezone import now

    from apps.users.models import SystemUser

    days = params.get("days_until_expiry", 1)
    deadline = now() + timedelta(days=days)
    return SystemUser.objects.filter(
        mtproto_keys__expired_date__lte=deadline,
        mtproto_keys__was_deleted=False,
    ).distinct()


def _not_subscribed(params: dict) -> QuerySet:
    from apps.users.models import SystemUser

    return SystemUser.objects.filter(is_active=True)
```

- [ ] **Step 5: Реализовать резолверы**

```python
# src/apps/notifications/resolvers.py
from __future__ import annotations

from typing import TYPE_CHECKING

from apps.notifications.enums import ContextResolverType

if TYPE_CHECKING:
    from apps.users.models import SystemUser


def resolve_context(*, resolver_type: int, user: SystemUser) -> dict | None:
    """Возвращает персональный контекст для пользователя, или None если данных нет."""
    if resolver_type == ContextResolverType.NONE:
        return {}

    resolvers = {
        ContextResolverType.ACTIVE_KEY_LINK: _resolve_active_key_link,
    }
    return resolvers[resolver_type](user)


def _resolve_active_key_link(user: SystemUser) -> dict | None:
    from apps.vds.selectors import get_active_key

    key = get_active_key(user=user)
    if key is None:
        return None
    return {"link": key.get_proxy_link()}
```

- [ ] **Step 6: Запустить тесты**

Run: `make test ARGS="apps.notifications.tests.test_selectors apps.notifications.tests.test_resolvers"`
Expected: OK

---

### Task 7: `SendNotificationService`

**Files:**
- Create: `src/apps/notifications/services/__init__.py`
- Create: `src/apps/notifications/services/send_notification_service.py`
- Create: `src/apps/notifications/tests/test_send_notification_service.py`

- [ ] **Step 1: Написать тест**

```python
# src/apps/notifications/tests/test_send_notification_service.py
from __future__ import annotations

from unittest import mock

from django.test import TestCase

from apps.notifications.services.send_notification_service import SendNotificationService
from apps.notifications.tests.factories import NotificationTemplateFactory


class TestSendNotificationService(TestCase):
    @mock.patch("apps.notifications.services.send_notification_service.send")
    def test_sends_rendered_template(self, mock_send: mock.Mock) -> None:
        NotificationTemplateFactory(
            slug="test-notify",
            text="Привет, ссылка: {link}",
            button_text="Подключиться",
            button_url="{link}",
        )

        service = SendNotificationService(
            slug="test-notify",
            context={"link": "https://example.com"},
        )
        service(chat_id=123)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["chat_id"], 123)
        self.assertIn("https://example.com", call_kwargs["text"])
        self.assertIsNotNone(call_kwargs["markup"])

    @mock.patch("apps.notifications.services.send_notification_service.send")
    def test_sends_template_without_button(self, mock_send: mock.Mock) -> None:
        NotificationTemplateFactory(
            slug="no-button",
            text="Простое сообщение",
            button_text="",
            button_url="",
        )

        service = SendNotificationService(slug="no-button", context={})
        service(chat_id=456)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["text"], "Простое сообщение")
        self.assertIsNone(call_kwargs["markup"])
```

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `make test ARGS="apps.notifications.tests.test_send_notification_service"`
Expected: FAIL

- [ ] **Step 3: Реализовать сервис**

```python
# src/apps/notifications/services/__init__.py
from apps.notifications.services.send_notification_service import SendNotificationService

__all__ = ["SendNotificationService"]
```

```python
# src/apps/notifications/services/send_notification_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import final

from apps.core.service import log_service_error
from apps.core.telegram.transport import send
from apps.notifications.selectors import get_template


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class SendNotificationService:
    slug: str
    context: dict

    @log_service_error
    def __call__(self, *, chat_id: int) -> None:
        template = get_template(slug=self.slug)
        message = template.render(context=self.context)
        send(chat_id=chat_id, text=message.text, markup=message.markup)
```

- [ ] **Step 4: Запустить тесты**

Run: `make test ARGS="apps.notifications.tests.test_send_notification_service"`
Expected: OK (2 tests)

---

### Task 8: `SendMailingService`

**Files:**
- Create: `src/apps/notifications/services/send_mailing_service.py`
- Create: `src/apps/notifications/tests/test_send_mailing_service.py`
- Modify: `src/apps/notifications/services/__init__.py`

- [ ] **Step 1: Написать тест**

```python
# src/apps/notifications/tests/test_send_mailing_service.py
from __future__ import annotations

from unittest import mock

from django.test import TestCase

from apps.notifications.enums import ContextResolverType, FilterType, MailingStatus
from apps.notifications.services.send_mailing_service import SendMailingService
from apps.notifications.tests.factories import MailingFactory, NotificationTemplateFactory
from apps.users.tests.factories import SystemUserFactory


class TestSendMailingService(TestCase):
    @mock.patch("apps.notifications.services.send_mailing_service.send")
    def test_sends_to_all_active_users(self, mock_send: mock.Mock) -> None:
        user1 = SystemUserFactory(username="111", is_active=True)
        user2 = SystemUserFactory(username="222", is_active=True)
        SystemUserFactory(username="333", is_active=False)

        template = NotificationTemplateFactory(
            slug="mailing-test",
            text="Привет всем!",
            button_text="",
            button_url="",
        )
        mailing = MailingFactory(
            template=template,
            filter_type=FilterType.ALL_ACTIVE,
            context_resolver=ContextResolverType.NONE,
            status=MailingStatus.DRAFT,
        )

        SendMailingService(mailing=mailing)()

        self.assertEqual(mock_send.call_count, 2)
        mailing.refresh_from_db()
        self.assertEqual(mailing.status, MailingStatus.COMPLETED)
        self.assertIsNotNone(mailing.sent_at)

    @mock.patch("apps.notifications.services.send_mailing_service.send")
    def test_skips_users_with_no_resolved_context(self, mock_send: mock.Mock) -> None:
        SystemUserFactory(username="444", is_active=True)

        template = NotificationTemplateFactory(
            slug="mailing-skip",
            text="Ссылка: {link}",
            button_text="",
            button_url="",
        )
        mailing = MailingFactory(
            template=template,
            filter_type=FilterType.ALL_ACTIVE,
            context_resolver=ContextResolverType.ACTIVE_KEY_LINK,
            status=MailingStatus.DRAFT,
        )

        SendMailingService(mailing=mailing)()

        mock_send.assert_not_called()
        mailing.refresh_from_db()
        self.assertEqual(mailing.status, MailingStatus.COMPLETED)

    @mock.patch("apps.notifications.services.send_mailing_service.send")
    def test_merges_static_and_personal_context(self, mock_send: mock.Mock) -> None:
        user = SystemUserFactory(username="555", is_active=True)

        template = NotificationTemplateFactory(
            slug="mailing-merge",
            text="Привет! Промо: {promo}",
            button_text="",
            button_url="",
        )
        mailing = MailingFactory(
            template=template,
            filter_type=FilterType.ALL_ACTIVE,
            context={"promo": "SALE2026"},
            context_resolver=ContextResolverType.NONE,
            status=MailingStatus.DRAFT,
        )

        SendMailingService(mailing=mailing)()

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        self.assertIn("SALE2026", call_kwargs["text"])
```

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `make test ARGS="apps.notifications.tests.test_send_mailing_service"`
Expected: FAIL

- [ ] **Step 3: Реализовать сервис**

```python
# src/apps/notifications/services/send_mailing_service.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from apps.core.service import log_service_error
from apps.core.telegram.transport import send
from apps.notifications.resolvers import resolve_context
from apps.notifications.selectors import get_users_by_filter

if TYPE_CHECKING:
    from apps.notifications.models import Mailing


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class SendMailingService:
    mailing: Mailing

    @log_service_error
    def __call__(self) -> None:
        mailing = self.mailing
        mailing.mark_as_sending()

        users = get_users_by_filter(
            filter_type=mailing.filter_type,
            params=mailing.filter_params,
        )
        template = mailing.template

        for user in users.iterator():
            personal_context = resolve_context(
                resolver_type=mailing.context_resolver,
                user=user,
            )
            if personal_context is None:
                continue
            merged_context = {**mailing.context, **personal_context}
            message = template.render(context=merged_context)
            send(
                chat_id=int(user.username),
                text=message.text,
                markup=message.markup,
            )
            time.sleep(0.05)

        mailing.mark_as_completed()
```

- [ ] **Step 4: Обновить `__init__.py`**

```python
# src/apps/notifications/services/__init__.py
from apps.notifications.services.send_mailing_service import SendMailingService
from apps.notifications.services.send_notification_service import SendNotificationService

__all__ = ["SendNotificationService", "SendMailingService"]
```

- [ ] **Step 5: Запустить тесты**

Run: `make test ARGS="apps.notifications.tests.test_send_mailing_service"`
Expected: OK (3 tests)

---

### Task 9: Admin, Celery-таска, обновление декоратора `log_infra_error`

**Files:**
- Create: `src/apps/notifications/admin.py`
- Create: `src/apps/notifications/tasks.py`
- Modify: `src/apps/core/service.py:67-73` — добавить `send_sorry` в `log_infra_error`

- [ ] **Step 1: Создать admin.py**

```python
# src/apps/notifications/admin.py
from __future__ import annotations

from django.contrib import admin

from apps.notifications.models import Mailing, NotificationTemplate
from apps.notifications.tasks import send_mailing_task


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("slug", "title")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Mailing)
class MailingAdmin(admin.ModelAdmin):
    list_display = ("template", "filter_type", "status", "created_at", "sent_at")
    list_filter = ("status", "filter_type")
    readonly_fields = ("status", "sent_at", "created_at", "updated_at")
    actions = ["send_mailing"]

    @admin.action(description="Отправить рассылку")
    def send_mailing(self, request, queryset) -> None:
        from apps.notifications.enums import MailingStatus

        for mailing in queryset.filter(status=MailingStatus.DRAFT):
            send_mailing_task.delay(mailing.id)
        self.message_user(request, f"Запущено рассылок: {queryset.count()}")
```

- [ ] **Step 2: Создать Celery-таску**

```python
# src/apps/notifications/tasks.py
from __future__ import annotations

from celery import shared_task


@shared_task
def send_mailing_task(mailing_id: int) -> None:
    from apps.notifications.selectors import get_mailing_by_id
    from apps.notifications.services.send_mailing_service import SendMailingService

    mailing = get_mailing_by_id(mailing_id=mailing_id)
    SendMailingService(mailing=mailing)()
```

- [ ] **Step 3: Добавить `send_sorry` в декоратор `log_infra_error`**

В файле `src/apps/core/service.py` обновить декоратор `log_infra_error`:

```python
def log_infra_error(__call__: Callable) -> Callable:
    @wraps(__call__)
    def wrapper(self, **kwargs) -> Any:
        try:
            return __call__(self, **kwargs)
        except BaseInfraError as infra_error:
            from apps.notifications.services.send_notification_service import (
                SendNotificationService,
            )

            SendNotificationService(
                slug="sorry_server_error", context={},
            )(chat_id=int(infra_error.telegram_id))
            _log_infra_error(infra_error)
            raise infra_error

    return wrapper
```

- [ ] **Step 4: Запустить все тесты**

Run: `make test`
Expected: OK

---

### Task 10: Обновление вызовов в `apps/users/`

**Files:**
- Modify: `src/apps/users/tasks.py:7,21,23,48`
- Modify: `src/apps/users/api/v1/views/first_free_link_view.py:6,22,36`

- [ ] **Step 1: Обновить `users/tasks.py`**

Заменить содержимое `src/apps/users/tasks.py`:

```python
# src/apps/users/tasks.py
import time
from time import sleep

from celery import shared_task
from django.db import transaction

from apps.core.telegram.transport import is_channel_member, send
from apps.notifications.selectors import get_template
from apps.users.models import SystemUser
from apps.users.services import get_first_free_link_service
from apps.vds.models import MTPRotoKey


@shared_task
def send_invite_to_chat_task(telegram_ids: list[str]) -> None:
    if not telegram_ids:
        telegram_ids = SystemUser.objects.filter(
            first_month_free_used=True
        ).values_list("username", flat=True)
    template = get_template(slug="invite_to_channel")
    for user in telegram_ids:
        try:
            if not is_channel_member(telegram_id=int(user)):
                message = template.render()
                send(
                    chat_id=int(user),
                    text=message.text,
                    markup=message.markup,
                )
                sleep(0.666)
        except Exception:
            ...


@shared_task
def send_free_link_to_user_task(telegram_ids: list[str]) -> None:
    template = get_template(slug="proxy_link_with_message")
    for telegram_id in telegram_ids:
        user = SystemUser.objects.get(username=telegram_id)
        if user.first_month_free_used:
            continue
        try:
            with transaction.atomic():
                MTPRotoKey.objects.filter(user=user).delete()
                response = get_first_free_link_service()(username=telegram_id)

                text = (
                    "✨ <b>Привет!</b>\n\n"
                    "🔥 Мы сгенерировали для тебя ссылку сроком действия до <b>{expired_date}</b> \n\n"
                    "⚡️ Попробуй — с ней мессенджер работает быстрее!\n\n"
                    "👀 Пожалуйста, подпишись на канал @mtproto_keys — там вся информация по развитию проекта\n\n"
                    "👇 <b>Твоя ссылка:</b>"
                ).format(expired_date=response.expired_date)

                message = template.render(
                    context={"text": text, "link": response.link},
                )
                send(
                    chat_id=int(telegram_id),
                    text=message.text,
                    markup=message.markup,
                    timeout=settings.TELEGRAM_TIMEOUT,
                )
                user.first_month_free_used = True
                if user.invited_from_username:
                    user.referral_activated = True
                user.save(update_fields=["first_month_free_used", "referral_activated"])
                time.sleep(0.666)
        except Exception:
            pass
```

**Замечание:** В `send_free_link_to_user_task` нужно добавить `from django.conf import settings` в начало файла для `settings.TELEGRAM_TIMEOUT`.

Обновлённый импорт-блок:

```python
import time
from time import sleep

from celery import shared_task
from django.conf import settings
from django.db import transaction

from apps.core.telegram.transport import is_channel_member, send
from apps.notifications.selectors import get_template
from apps.users.models import SystemUser
from apps.users.services import get_first_free_link_service
from apps.vds.models import MTPRotoKey
```

- [ ] **Step 2: Обновить `first_free_link_view.py`**

Убрать импорт и декоратор `notify_bad_request`. Файл `src/apps/users/api/v1/views/first_free_link_view.py`:

```python
# src/apps/users/api/v1/views/first_free_link_view.py
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.api.v1.serializers import (
    CheckFirstFreeLinkSerializer,
    FirstFreeLinkSerializer,
)
from apps.users.permissions import BotAuthToken
from apps.users.services import get_first_free_link_service
from apps.users.services.check_first_free_link_service import (
    get_check_first_free_link_service,
)
from apps.users.services.dtos import CheckFirstFreeLinkIn


class CreateFirstFreeLinkView(APIView):
    permission_classes = (BotAuthToken,)

    def post(self, request: Request) -> Response:
        serializer = FirstFreeLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = get_first_free_link_service()
        result = service(username=serializer.validated_data["username"])

        return Response(data=result.asdict(), status=status.HTTP_200_OK)


class CheckFirstFreeLinkView(APIView):
    permission_classes = (BotAuthToken,)

    def post(self, request: Request) -> Response:
        serializer = CheckFirstFreeLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = get_check_first_free_link_service()
        result = service(data=CheckFirstFreeLinkIn(**serializer.validated_data))
        return Response(
            data={"available_free_period": result},
            status=status.HTTP_200_OK,
        )
```

- [ ] **Step 3: Запустить тесты users**

Run: `make test ARGS="apps.users"`
Expected: OK

---

### Task 11: Обновление вызовов в `apps/payments/`

**Files:**
- Modify: `src/apps/payments/services/notify_payment_service.py`
- Modify: `src/apps/payments/tests/test_notify_payment_service.py`

- [ ] **Step 1: Обновить `notify_payment_service.py`**

```python
# src/apps/payments/services/notify_payment_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from apps.notifications.services.send_notification_service import SendNotificationService

if TYPE_CHECKING:
    from apps.users.models import SystemUser
    from apps.vds.models import MTPRotoKey


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class NotifyPaymentService:
    """Отправляет пользователю прокси-ссылку через Telegram после оплаты."""

    def __call__(self, *, user: SystemUser, key: MTPRotoKey) -> None:
        SendNotificationService(
            slug="proxy_purchased",
            context={"link": key.get_proxy_link()},
        )(chat_id=int(user.username))


def get_notify_payment_service() -> NotifyPaymentService:
    return NotifyPaymentService()
```

- [ ] **Step 2: Обновить тест**

```python
# src/apps/payments/tests/test_notify_payment_service.py
from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.notifications.tests.factories import NotificationTemplateFactory
from apps.payments.services.notify_payment_service import get_notify_payment_service
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestNotifyPaymentService(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory(username="12345")
        self.vds = VDSInstanceFactory()
        self.service = get_notify_payment_service()
        NotificationTemplateFactory(
            slug="proxy_purchased",
            text=(
                "🎉 <b>Спасибо за покупку!</b>\n\n"
                "✨ Ваш VPN-ключ готов к использованию.\n"
                "👉 Нажмите кнопку <b>«🇳🇱 Подключиться»</b> ниже.\n\n"
                "⏳ <b>Важно:</b> ссылка действует <b>30 дней</b> с момента покупки.\n"
                "🗓 После этого срока доступ потребуется продлить."
            ),
            button_text="🇳🇱 Подключиться",
            button_url="{link}",
        )

    @mock.patch("apps.notifications.services.send_notification_service.send")
    def test_sends_proxy_link_to_user(self, mock_send: mock.Mock) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=30),
            was_deleted=False,
        )

        self.service(user=self.user, key=key)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["chat_id"], 12345)
        self.assertIsNotNone(call_kwargs["markup"])
```

- [ ] **Step 3: Запустить тесты payments**

Run: `make test ARGS="apps.payments"`
Expected: OK

---

### Task 12: Обновление вызовов в `apps/vds/tasks.py`

**Files:**
- Modify: `src/apps/vds/tasks.py` — полная замена

- [ ] **Step 1: Обновить `vds/tasks.py`**

Заменить содержимое `src/apps/vds/tasks.py`:

```python
# src/apps/vds/tasks.py
import time
from datetime import timedelta

import requests
from celery import shared_task
from django.conf import settings
from django.utils import html, timezone

from apps.core.telegram.transport import send
from apps.notifications.selectors import get_template
from apps.vds.models import MTPRotoKey, VDSInstance


@shared_task
def migrate_vds_keys_task(from_instance_id: int) -> None:
    server = VDSInstance.objects.get(pk=from_instance_id)
    keys = server.keys.all().select_related("user")
    for key in keys:
        for server in VDSInstance.objects.exclude(pk=from_instance_id):
            try:
                if not getattr(key.user, "username", None):
                    continue
                if not key.token:
                    continue
                requests.post(
                    url=f"{server.internal_url}/api/users",
                    json={"username": key.user.username, "secret": key.token},
                    timeout=settings.VDS_REQUEST_TIMEOUT,
                )
            except Exception as exc:
                escaped_error = html.escape(str(exc))
                send(
                    chat_id=int(settings.MY_TELEGRAM_ID),
                    text=(
                        "🔴 <b>(BACKEND) Системное оповещение</b>\n\n"
                        "🛡 <b>Тип ошибки:</b> SERVER INTERNAL ERROR (500)\n"
                        "📋 <b>Детали:</b>\n"
                        f"- Не удалось добавить перенести ключ на сервер\n"
                        f"- Сервер — <b>{server.internal_url}</b>\n"
                        f"- Порядковый номер сервера — <b>#{server.number}</b>\n"
                        f"- Пользователь — <b>{key.user.username}</b>\n"
                        f"- Ключ — <b>{key}</b>\n\n"
                        f"<code>{escaped_error}</code>\n\n"
                        "⚙️ <i>Требуется внимание команды!</i>"
                    ),
                )

        time.sleep(0.5)


@shared_task
def remove_user_keys_daily():
    from apps.vds.services import get_remove_user_key_infra_service

    queryset = MTPRotoKey.objects.active().expired_today()
    usernames = list(queryset.values_list("user__username", flat=True).distinct())
    if not usernames:
        return
    service = get_remove_user_key_infra_service()
    for server in VDSInstance.objects.all():
        service(server=server, keys=queryset)
    queryset.update(is_active=False, was_deleted=True)
    template = get_template(slug="link_deactivated")
    for username in usernames:
        try:
            message = template.render()
            send(chat_id=int(username), text=message.text, markup=message.markup)
            time.sleep(1)
        except Exception as exc:
            escaped_error = html.escape(str(exc))
            send(
                chat_id=int(settings.MY_TELEGRAM_ID),
                text=(
                    "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                    "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                    "📋 <b>Детали:</b>\n"
                    f"- Не удалось уведомить пользователя об удалении ссылки\n"
                    f"- Пользователь — {username}\n\n"
                    f"<code>{escaped_error}</code>\n\n"
                    "⚙️ <i>Возможно, требуется внимание команды</i>"
                ),
            )


@shared_task
def notify_before_removing_daily():
    target_date = (timezone.now() + timedelta(days=1)).date()

    queryset = MTPRotoKey.objects.active().filter(
        expired_date__date=target_date,
        user_notified=False,
    )

    template = get_template(slug="before_expiry_1day")
    already_sent = set()
    for key in queryset:
        username = None
        try:
            username = getattr(key.user, "username", None)
            if not username:
                continue
            if username in already_sent:
                continue
            message = template.render()
            send(chat_id=int(username), text=message.text, markup=message.markup)
            already_sent.add(username)
            key.user_notified = True
            key.save(update_fields=["user_notified"])
            time.sleep(1)
        except Exception as exc:
            escaped_error = html.escape(str(exc))
            send(
                chat_id=int(settings.MY_TELEGRAM_ID),
                text=(
                    "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                    "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                    "📋 <b>Детали:</b>\n"
                    f"- Не удалось уведомить пользователя о завтрашнем удалении ссылки.\n"
                    f"- Пользователь — {username}\n\n"
                    f"<code>{escaped_error}</code>\n\n"
                    "⚙️ <i>Возможно, требуется внимание команды</i>"
                ),
            )



@shared_task
def notify_before_removing_daily_hour_before():
    queryset = MTPRotoKey.objects.active().filter(expired_date__date=timezone.now().date())

    template = get_template(slug="before_expiry_1hour")
    already_sent = set()
    for key in queryset:
        username = None
        try:
            username = getattr(key.user, "username", None)
            if not username:
                continue
            if username in already_sent:
                continue
            message = template.render()
            send(chat_id=int(username), text=message.text, markup=message.markup)
            already_sent.add(username)
            time.sleep(1)
        except Exception as exc:
            escaped_error = html.escape(str(exc))
            send(
                chat_id=int(settings.MY_TELEGRAM_ID),
                text=(
                    "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                    "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                    "📋 <b>Детали:</b>\n"
                    f"- Не удалось уведомить пользователя о завтрашнем удалении ссылки.\n"
                    f"- Пользователь — {username}\n\n"
                    f"<code>{escaped_error}</code>\n\n"
                    "⚙️ <i>Возможно, требуется внимание команды</i>"
                ),
            )




@shared_task
def add_key_to_another_vds_instances_task(exclude: int, username: str, secret: str):
    servers = VDSInstance.objects.exclude(pk=exclude)
    for server in servers:
        try:
            response = requests.post(
                url=f"{server.internal_url}/api/users",
                json={"username": username, "secret": secret},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except Exception as exc:
            escaped_error = html.escape(str(exc))
            send(
                chat_id=int(settings.MY_TELEGRAM_ID),
                text=(
                    "🔴 <b>(BACKEND) Системное оповещение</b>\n\n"
                    "🛡 <b>Тип ошибки:</b> SERVER INTERNAL ERROR (500)\n"
                    "📋 <b>Детали:</b>\n"
                    f"- Не удалось добавить пользователя на сервер\n"
                    f"- Сервер — <b>{server.internal_url}</b>\n"
                    f"- Порядковый номер сервера — <b>#{server.number}</b>\n"
                    f"- Пользователь — <b>{username}</b>\n\n"
                    f"<code>{escaped_error}</code>\n\n"
                    "⚙️ <i>Требуется внимание команды!</i>"
                ),
            )


@shared_task
def remove_key_from_another_vds_instances_task(server: int, keys_id: list[int]) -> None:
    server = VDSInstance.objects.get(pk=server)
    keys = MTPRotoKey.objects.filter(pk__in=keys_id)
    usernames = list(keys.values_list("user__username", flat=True))
    try:
        response = requests.delete(
            url=f"{server.internal_url}/api/users",
            json={"usernames": usernames},
            timeout=settings.VDS_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        keys.update(was_deleted=True, is_active=False)
    except Exception as exc:
        escaped_error = html.escape(str(exc))
        send(
            chat_id=int(settings.MY_TELEGRAM_ID),
            text=(
                "🔴 <b>(BACKEND) Системное оповещение</b>\n\n"
                "🛡 <b>Тип ошибки:</b> SERVER INTERNAL ERROR (500)\n"
                "📋 <b>Детали:</b>\n"
                f"- Не удалось удалить ключ пользователей с сервера\n"
                f"- Сервер — <b>{server.internal_url}</b>\n"
                f"- Порядковый номер сервера — <b>#{server.number}</b>\n"
                f"- Пользователи — <b>{usernames}</b>\n\n"
                f"<code>{escaped_error}</code>\n\n"
                "⚙️ <i>Требуется внимание команды!</i>"
            ),
        )


@shared_task
def broadcast_proxy_links_task(testing: bool = False) -> None:
    from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

    if testing:
        keys = MTPRotoKey.objects.filter(
            user__pk=562,
            is_active=True,
            was_deleted=False,
        ).select_related("user")
    else:
        keys = (
            MTPRotoKey.objects.filter(
                is_active=True,
                was_deleted=False,
                user__first_month_free_used=True,
                expired_date__gt=timezone.now(),
            )
            .select_related("user")
        )

    sent_count = 0
    for key in keys:
        try:
            send(
                chat_id=int(key.user.username),
                text=(
                    "✨ <b>Привет!</b>\n\n"
                    "В последнее время часть ссылок могла работать нестабильно из-за блокировок. "
                    "Мы долго работали над решением — и нам удалось <b>полностью обойти ограничения.</b>\n\n"
                    "Сейчас всё работает стабильно, и мы решили продлить твою ссылку на <b>3 дня</b> "
                    "в качестве компенсации за неудобства.\n\n"
                    f"👇 <b>Твоя ссылка (действует до {(key.expired_date + timedelta(days=3)).strftime('%d.%m.%Y')}):</b>"
                ),
                markup=InlineKeyboardMarkup(
                    keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🇳🇱 Подключиться",
                                url=key.get_proxy_link(),
                            )
                        ]
                    ]
                ),
            )
            key.expired_date = key.expired_date + timedelta(days=3)
            key.save(update_fields=["expired_date"])
            sent_count += 1
            if sent_count % 10 == 0:
                time.sleep(1)
        except Exception as exc:
            try:
                escaped_error = html.escape(str(exc))
                send(
                    chat_id=int(settings.MY_TELEGRAM_ID),
                    text=(
                        "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                        "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                        "📋 <b>Детали:</b>\n"
                        f"- Не удалось отправить broadcast пользователю\n"
                        f"- Пользователь — {key.user.username}\n\n"
                        f"<code>{escaped_error}</code>\n\n"
                        "⚙️ <i>Возможно, требуется внимание команды</i>"
                    ),
                )
            except Exception:
                pass
```

- [ ] **Step 2: Запустить тесты vds**

Run: `make test ARGS="apps.vds"`
Expected: OK

---

### Task 13: Удаление `apps/core/bot.py` и финальная проверка

**Files:**
- Delete: `src/apps/core/bot.py`

- [ ] **Step 1: Проверить что нет оставшихся импортов из `apps.core.bot`**

Run: `cd src && grep -r "from apps.core.bot" --include="*.py" .`
Expected: пустой вывод (все импорты обновлены)

Run: `cd src && grep -r "apps.core.bot" --include="*.py" .`
Expected: пустой вывод

- [ ] **Step 2: Удалить `apps/core/bot.py`**

Удалить файл `src/apps/core/bot.py`.

- [ ] **Step 3: Запустить полный набор тестов**

Run: `make test`
Expected: OK — все тесты проходят, нет регрессий

- [ ] **Step 4: Проверить что миграции корректны**

Run: `cd src && python manage.py migrate --check`
Expected: нет непримененных миграций
