# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Django backend for BeatVault — an MTProto proxy subscription service. Users receive Telegram proxy keys via a Telegram bot. The bot is a separate containerized service in `bot/`. All business user interaction happens through Telegram, not a web UI.

Подробная документация — в `docs/` (BUSINESS.md, ARCHITECTURE.md, CONTRACTS.md, MODELS.md).

## Commands

All Django commands run from `src/`:

```bash
cd src

# Run dev server
python manage.py runserver 0.0.0.0:8000

# Migrations
python manage.py migrate
python manage.py makemigrations

# Run all tests (from repo root, uses test_settings with suppressed logs)
make test

# Run a single test module
make test ARGS="apps.users.tests.test_first_free_link"

# Run a single test case
make test ARGS="apps.users.tests.test_first_free_link.TestFirstFreeLink.test_first_free_link_30days"
```

Production runs via Docker Compose:
```bash
docker-compose -f docker-compose.yml up -d        # production
docker-compose -f docker-compose.local.yml up -d  # local
```

## Architecture

### Service Layer

Two decorator types distinguish service kinds:
- `@log_service_error` — business logic errors, sends Telegram notification to user
- `@log_infra_error` — infra/VDS errors, sends "sorry" to user + admin notification

Services are plain frozen dataclasses (no DI container here, unlike the global CLAUDE.md pattern). Each service file defines a factory function at module level:

```python
def get_first_free_link_service() -> FirstFreeLinkService:
    return FirstFreeLinkService()
```

### Error Handling

`BaseServiceError` and `BaseInfraError` both accept `telegram_id` as first arg. The docstring is the user-facing message:

```python
class AlreadyUsedFree(BaseServiceError):
    """🔒 Вы уже получали бесплатную ссылку..."""
```

### Authentication

API endpoints authenticate via `Bot-Auth-Token` header (checked against `settings.BOT_AUTH_TOKEN`). This header must be included in test HTTP calls.

### VDS Infrastructure (reconcile model)

`VDSInstance` objects represent proxy servers — all equal mirrors; there is **no "home server"** and no `get_least_populated`. The DB is the single source of truth; a key's presence on servers is a derived cache.

Issuing/reissuing a key is a pure DB write (`IssueKeyService` / `UpdateKeyService`) — no synchronous HTTP, no server selection. A Celery task `push_key_to_servers_task(key_id)` then fans the secret out to **all healthy** VDS via idempotent POST (`409` → skip). A global cap `settings.GLOBAL_KEYS_LIMIT` is enforced in `IssueKeyService` (`KeysLimitReached`). Recovery of a downed server is handled by `check_vds_health_task → sync_keys_to_vds_task` (backfill of all active keys).

### Celery Tasks

Scheduled via Celery Beat (defined in `config/settings/celery.py`):
- `remove_user_keys_daily` — 9:00 UTC, deletes expired keys
- `notify_before_removing_daily` — 15:00 UTC, warns users
- `notify_before_removing_daily_hour_before` — 8:00 UTC, 1-hour pre-warning

### NotificationTemplate buttons

Кнопка шаблона — либо URL (`button_url`), либо callback (`button_callback_data`), не оба сразу. URL имеет приоритет. Используй `button_callback_data` когда уведомление должно открывать экран бота (например `"my_servers"`). Соответствующий aiogram-хендлер для этого `callback_data` должен существовать в `bot/src/handlers.py`.

### apps/music/ — FakeTLS-заглушка

Приложение `music/` — статическая заглушка без бизнес-логики. Она развёрнута на домене, под который маскируется FakeTLS прокси-сервера. Не изучать, не рефакторить, не трогать.

### Key Business Rules

- First free key: 30 days by default, 14 days if referred, 7 days if free quota (`FIRST_MONTH_LIMIT`) is exhausted
- Referral reward: after 5 referrals activate their free period, the referrer gets a free key (`GetFreeLinkViaReferralsService`)
- One `MTPRotoKey` is a single secret valid across the whole fleet (no per-key `vds`/`node_number`/`tls_domain`). It is delivered to **all healthy** VDS via the async `push_key_to_servers_task`. The FakeTLS masking domain lives in `settings.TLS_DOMAIN` (same on every VDS), baked into the secret by `get_secret_token()`.
- Issue/reissue services return only `expired_date` (DTOs have no `link`) — the bot shows a «📡 Мои серверы» button (`callback_data="my_servers"`) instead of a single link
- `GetMyServersService` generates proxy links on-the-fly for each active `VDSInstance` using the stored `token` + `VDSInstance.name` (the server's subdomain in `{name}.beatvault.ru`)
- `VDSInstance.location` holds the display label (e.g. `"🇳🇱 Нидерланды"`) shown as a button in the bot

### Models

Все новые модели наследуются от `BaseDjangoModel` (`apps/core/models.py`). Не дублировать поля `is_active`, `created_at`, `updated_at`. Фильтровать через `Model.objects.active()`, не через `filter(is_active=True)`.

## Rules

1. **Поддерживать документацию в актуальном виде.** При изменении бизнес-логики, контрактов или архитектуры — обновлять docstrings и соответствующие файлы в `docs/` (BUSINESS.md, ARCHITECTURE.md, CONTRACTS.md, MODELS.md).
2. **Всегда прогонять тесты.** После любых изменений запускать тесты и убедиться, что нет регрессий. Не считать задачу выполненной без зелёных тестов.
3. **Переиспользовать селекторы.** ORM-запросы живут в `selectors.py` — не дублировать их в сервисах. Перед написанием нового запроса проверить, есть ли подходящий селектор.
4. **Следовать SOLID, DRY, DDD.** Единая ответственность для сервисов, инъекция зависимостей через поля dataclass, доменные исключения в `exceptions.py`, enum в `enums.py`, DTO для передачи данных между слоями.
5. **Всегда использовать `from __future__ import annotations`.** Импорты, нужные только для аннотаций типов, выносить в блок `TYPE_CHECKING`:
   ```python
   from __future__ import annotations
   from typing import TYPE_CHECKING

   if TYPE_CHECKING:
       from apps.users.models import SystemUser
   ```

## Testing Patterns

Tests use `APITestCase` + `factory_boy` factories. VDS HTTP calls are mocked with the `responses` library:

```python
@responses.activate
def test_something(self):
    responses.add(method=responses.POST, url=..., json={...})
```

For tests that trigger `log_service_error` or bot notifications, patch `apps.core.bot.TelegramBot` methods to avoid real Telegram calls.

Factories live in `apps/{app}/tests/factories.py`. All test files are in `apps/{app}/tests/`.
