# Архитектура

## Место в системе

Этот репозиторий — **центральное звено** платформы. Содержит бизнес-логику, управление пользователями, платежи и реферальную программу. Telegram-бот живёт в поддиректории `bot/`.

```
Пользователь
    │
    ▼
Telegram Bot ─── (bot/)
    │
    ▼
Django Backend ── (src/)               ◄── Celery Beat (расписание)
    │                                       │
    ▼                                       ▼
VDS Instance #1 ── (my-mtproto-vds-instance)
VDS Instance #2
VDS Instance #N
    │
    ▼
telemt (MTProto-прокси)
```

**Telegram Bot** (`bot/`) — Aiogram 3.x, polling-режим. Принимает команды от пользователя, обрабатывает платежи. Общается с бэкендом через REST API с заголовком `Bot-Auth-Token`.

**Django Backend** (`src/`) — Django 6 + DRF. Бизнес-логика, управление ключами, платежи, рефералы. БД — SQLite. Фоновые задачи через Celery + Redis.

**VDS Instance** — FastAPI-сервис на каждом VDS-сервере. Принимает команды от Django и управляет прокси-сервером telemt.

## Стек

| Компонент | Технология |
|-----------|------------|
| Backend | Django 6.0.2, DRF 3.16.1, Python 3.13 |
| Bot | Aiogram 3.x (polling) |
| Очередь задач | Celery 5.6.2 + Redis 7 |
| Мониторинг Celery | Flower |
| Reverse proxy | Nginx (SSL termination) |
| БД | SQLite |
| Пакетный менеджер | uv |
| Деплой | Docker Compose |

## Структура проекта

```
src/
├── config/
│   ├── settings/
│   │   ├── base.py              # Основные настройки Django
│   │   ├── bot.py               # BOT_TOKEN, BOT_AUTH_TOKEN, BOT_LINK
│   │   ├── celery.py            # Broker, Beat Schedule
│   │   ├── vds.py               # VDS_REQUEST_TIMEOUT
│   │   ├── referrals.py         # INVITE_MUST_COUNT, REFERRAL_LINKS_LIMIT
│   │   ├── rest_framework_settings.py
│   │   └── logging_conf.py
│   ├── celery.py                # Инициализация Celery app
│   ├── urls.py
│   ├── middlewares.py           # RequestLoggingMiddleware
│   └── wsgi.py
├── apps/
│   ├── core/                    # BaseDjangoModel, исключения, декораторы, Telegram-транспорт
│   ├── notifications/           # Шаблоны уведомлений, рассылки
│   ├── users/                   # SystemUser, бесплатные ссылки, рефералы
│   ├── vds/                     # VDSInstance, MTPRotoKey, инфра-сервисы, Celery-задачи
│   ├── payments/                # Product, Payment, YuKassa/Stars
│   └── music/                   # Заглушка для FakeTLS-маскировки (не трогать, бизнес-логики нет)
└── manage.py

bot/
├── src/
│   ├── bot.py                   # Инициализация Aiogram
│   ├── handlers.py              # /start, оплата, рефералы, кнопки
│   ├── config.py                # Переменные окружения
│   ├── services/                # HTTP-клиенты к Django API
│   └── keyboards/               # Inline-клавиатуры
├── pyproject.toml
├── uv.lock
└── Dockerfile
```

## apps/core — Инфраструктурное ядро

```
apps/core/
├── exceptions.py       # BaseError, BaseServiceError, BaseInfraError
├── decorators.py       # @log_service_error, @log_infra_error
├── protocols.py        # IService — протокол для всех сервисов
├── models.py           # BaseDjangoModel, BaseServiceDTO
├── handle_error.py     # DRF exception handler
└── telegram/
    ├── transport.py    # send_telegram_message(), is_channel_member()
    └── error_logger.py # Отправка ошибок админу в Telegram
```

## Service Layer

Сервисы — frozen dataclasses с `__call__`. Два декоратора (из `apps.core.decorators`):

- `@log_service_error` — бизнес-ошибка → Telegram-уведомление пользователю
- `@log_infra_error` — инфра-ошибка → «извините» пользователю + алерт админу

Исключения (из `apps.core.exceptions`): `BaseServiceError`, `BaseInfraError`.

Каждый файл сервиса определяет фабричную функцию:

```python
def get_first_free_link_service() -> FirstFreeLinkService:
    return FirstFreeLinkService()
```

## apps/notifications — Уведомления и рассылки

```
apps/notifications/
├── models.py           # NotificationTemplate, Mailing, RenderedMessage
├── enums.py            # MailingStatus, FilterType, ContextResolverType
├── selectors.py        # get_template, get_mailing_by_id, get_users_by_filter
├── resolvers.py        # resolve_context — персональный контекст для шаблонов
├── services/
│   ├── send_notification_service.py  # Отправка одного уведомления по slug
│   └── send_mailing_service.py       # Массовая рассылка с фильтрами и счётчиками
└── tasks.py            # Celery-задача send_mailing_task
```

`NotificationTemplate` хранит HTML-текст с `{переменными}`, опциональную кнопку и флаг `include_payment_buttons` (добавляет кнопку "Поддержать" с `callback_data="boost_paid"`). Кнопка может быть URL (`button_url`) или callback (`button_callback_data`) — URL имеет приоритет.

`Mailing` отслеживает статусы: DRAFT → SENDING → COMPLETED / PARTIALLY_COMPLETED / FAILED. Поля `sent_count` и `failed_count` фиксируют результаты рассылки.

## Аутентификация

Все API-эндпоинты защищены заголовком `Bot-Auth-Token`, проверяемым через permission `BotAuthToken` против `settings.BOT_AUTH_TOKEN`.

## Деплой

Docker Compose с 7 сервисами:

| Сервис | Назначение | Порт |
|--------|------------|------|
| django | Django + Gunicorn | 8000 |
| nginx | Reverse proxy + SSL | 80, 443 |
| redis | Брокер Celery | 6379 |
| celery-worker | Обработка задач | — |
| celery-beat | Расписание задач | — |
| flower | Мониторинг Celery | 5555 |
| bot | Telegram-бот | — |

Все сервисы в общей bridge-сети `backend`.
