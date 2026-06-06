# Рефакторинг TelegramBot + приложение notifications

## Проблема

Класс `TelegramBot` в `apps/core/bot.py` нарушает SRP:
- Смешивает транспорт (отправка в Telegram), логирование ошибок для разработчика и пользовательские уведомления
- Дублирование: `notify_before_removing` / `notify_before_removing_before_hour` почти идентичны, `log_infra_error` / `log_service_error` — одинаковая структура
- Неиспользуемый метод `send_invite_to_chat`
- Пользовательские сообщения захардкожены — добавление нового требует правки кода
- Нет возможности управлять сообщениями и рассылками из админки

## Решение

Разделение на три слоя: транспорт (инфраструктура), логирование ошибок (инфраструктура), пользовательские уведомления (приложение с БД-шаблонами).

---

## 1. `apps/core/telegram/` — инфраструктурный слой

Функции, не классы (текущий `TelegramBot` — stateless, `@classmethod` повсюду).

### Структура

```
apps/core/telegram/
├── __init__.py      # реэкспорт send, is_channel_member, log_infra_error, log_service_error
├── transport.py     # send(), is_channel_member(), _LazyBot
└── error_logger.py  # log_infra_error(), log_service_error()
```

### `transport.py`

```python
from __future__ import annotations

from django.conf import settings
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup


class _LazyBot:
    """Прокси, создающий TeleBot при первом обращении."""
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

### `error_logger.py`

```python
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

### Обновление декораторов

`apps/core/service.py`: декораторы `@log_service_error` и `@log_infra_error` обновляют импорты:

```python
# Было
from apps.core.bot import TelegramBot
TelegramBot.log_service_error(exc)
TelegramBot.send_sorry(exc)

# Стало
from apps.core.telegram.error_logger import log_service_error, log_infra_error
from apps.notifications.services.send_notification_service import SendNotificationService

log_service_error(exc)
SendNotificationService(slug="sorry_server_error", context={})(chat_id=exc.telegram_id)
```

### Удаляется

- `send_invite_to_chat` — не используется нигде
- `log_bad_request` — избыточен: валидация входных данных — штатная работа DRF, бэкенд не должен уведомлять разработчика о невалидных запросах клиента
- Декоратор `notify_bad_request` — удаляется вместе с `log_bad_request`. Вызовы декоратора в `apps/users/api/v1/views/first_free_link_view.py` убираются

---

## 2. `apps/notifications/` — пользовательские уведомления

### Структура

```
apps/notifications/
├── models.py
├── enums.py
├── selectors.py
├── resolvers.py
├── admin.py
├── tasks.py
├── apps.py
├── migrations/
│   ├── 0001_initial.py             # структурная миграция
│   └── 0002_seed_templates.py      # data-миграция с существующими шаблонами
└── services/
    ├── __init__.py
    ├── send_notification_service.py
    └── send_mailing_service.py
```

### `enums.py`

```python
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

### `models.py`

Обе модели наследуются от `BaseDjangoModel` (`apps/core/models.py`), который даёт `is_active`, `created_at`, `updated_at` и `ActiveQuerySet` (метод `.active()`) из коробки.

```python
from __future__ import annotations

from django.db import models

from apps.core.models import BaseDjangoModel
from apps.notifications.enums import ContextResolverType, FilterType, MailingStatus


class NotificationTemplate(BaseDjangoModel):
    slug = models.SlugField("Идентификатор", max_length=64, unique=True)
    title = models.CharField("Название", max_length=255)
    text = models.TextField("Текст сообщения (HTML, поддерживает {переменные})")
    button_text = models.CharField("Текст кнопки", max_length=128, blank=True, default="")
    button_url = models.CharField("URL кнопки (поддерживает {переменные})", max_length=512, blank=True, default="")

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
                    [InlineKeyboardButton(
                        text=self.button_text,
                        url=self.button_url.format(**ctx),
                    )]
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
    filter_params = models.JSONField("Параметры фильтра", default=dict, blank=True)
    context = models.JSONField("Статический контекст для шаблона", default=dict, blank=True)
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

### `selectors.py`

```python
from __future__ import annotations

from django.db.models import QuerySet

from apps.notifications.enums import FilterType
from apps.notifications.models import NotificationTemplate


def get_template(*, slug: str) -> NotificationTemplate:
    return NotificationTemplate.objects.active().get(slug=slug)


def get_mailing_by_id(*, mailing_id: int) -> Mailing:
    return Mailing.objects.select_related("template").get(id=mailing_id)


def get_users_by_filter(*, filter_type: int, params: dict) -> QuerySet:
    from apps.users.models import SystemUser

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
    from django.utils.timezone import now
    from datetime import timedelta
    from apps.users.models import SystemUser

    days = params.get("days_until_expiry", 1)
    deadline = now() + timedelta(days=days)
    return SystemUser.objects.filter(
        mtproto_keys__expired_date__lte=deadline,
        mtproto_keys__was_deleted=False,
    ).distinct()


def _not_subscribed(params: dict) -> QuerySet:
    # Фильтрация на стороне Telegram API, не через ORM
    # Реализация: получить всех активных, проверить через is_channel_member
    from apps.users.models import SystemUser
    return SystemUser.objects.filter(is_active=True)
```

### `resolvers.py`

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from apps.notifications.enums import ContextResolverType

if TYPE_CHECKING:
    from apps.users.models import SystemUser


def resolve_context(*, resolver_type: int, user: SystemUser) -> dict | None:
    """Возвращает персональный контекст для пользователя, или None если данных нет (пользователь будет пропущен)."""
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
    return {"link": key.link}
```

### `services/send_notification_service.py`

```python
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

### `services/send_mailing_service.py`

```python
from __future__ import annotations

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
            send(chat_id=user.telegram_id, text=message.text, markup=message.markup)
            time.sleep(0.05)  # Telegram Bot API rate limit: ~30 msg/sec

        mailing.mark_as_completed()
```

### `tasks.py`

```python
from __future__ import annotations

from celery import shared_task


@shared_task
def send_mailing_task(mailing_id: int) -> None:
    from apps.notifications.selectors import get_mailing_by_id
    from apps.notifications.services.send_mailing_service import SendMailingService

    mailing = get_mailing_by_id(mailing_id=mailing_id)
    SendMailingService(mailing=mailing)()
```

### `admin.py`

Admin action "Отправить рассылку" запускает `send_mailing_task.delay(mailing.id)`.

---

## 3. Data-миграция существующих шаблонов

`0002_seed_templates.py` — создаёт `NotificationTemplate` для каждого существующего пользовательского сообщения из `TelegramBot`:

| slug | Источник |
|------|----------|
| `invite_to_channel` | `send_invite_to_chat_v2` |
| `before_expiry_1day` | `notify_before_removing` |
| `before_expiry_1hour` | `notify_before_removing_before_hour` |
| `link_deactivated` | `send_message_deactivate_link` |
| `proxy_purchased` | `send_proxy_link` |
| `proxy_link_with_message` | `send_message_with_link` |
| `sorry_server_error` | `send_sorry` |

Шаблоны создаются автоматически при деплое — нулевой downtime.

---

## 4. Обновление вызовов

Все места, использующие `TelegramBot.send_proxy_link(...)`, `TelegramBot.notify_before_removing(...)` и т.д., заменяются на:

```python
template = get_template(slug="proxy_purchased")
message = template.render(context={"link": link})
send(chat_id=chat_id, text=message.text, markup=message.markup)
```

Или через `SendNotificationService`:

```python
SendNotificationService(slug="proxy_purchased", context={"link": link})(chat_id=chat_id)
```

---

## 5. Что удаляется

- `apps/core/bot.py` — полностью (заменён на `apps/core/telegram/` + `apps/notifications/`)
- `TelegramBot` класс
- Декоратор `notify_bad_request` и функция `log_bad_request` — удаляются без замены
- Вызовы `@notify_bad_request` в `apps/users/api/v1/views/first_free_link_view.py` — убираются
