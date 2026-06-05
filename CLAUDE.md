# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Django backend for BeatVault — an MTProto proxy subscription service. Users receive Telegram proxy keys via a Telegram bot. The bot is a separate containerized service in `bot/`. All business user interaction happens through Telegram, not a web UI.

Подробная документация — в `docs/` (BUSINESS.md, ARCHITECTURE.md, CONTRACTS.md, MODELS.md, SERVICES.md).

## Commands

All Django commands run from `src/`:

```bash
cd src

# Run dev server
python manage.py runserver 0.0.0.0:8000

# Migrations
python manage.py migrate
python manage.py makemigrations

# Run all tests
python manage.py test

# Run a single test module
python manage.py test apps.users.tests.test_first_free_link

# Run a single test case
python manage.py test apps.users.tests.test_first_free_link.TestFirstFreeLink.test_first_free_link_30days
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

### VDS Infrastructure

`VDSInstance` objects represent proxy servers. `VDSInstance.objects.get_least_populated()` picks the server with fewest active keys. `AddNewKeyInfraService` calls the VDS REST API to create a key, then fires a Celery task to replicate it to other VDS nodes.

### Celery Tasks

Scheduled via Celery Beat (defined in `config/settings/celery.py`):
- `remove_user_keys_daily` — 9:00 UTC, deletes expired keys
- `notify_before_removing_daily` — 15:00 UTC, warns users
- `notify_before_removing_daily_hour_before` — 8:00 UTC, 1-hour pre-warning

### apps/music/ — FakeTLS-заглушка

Приложение `music/` — статическая заглушка без бизнес-логики. Она развёрнута на домене, под который маскируется FakeTLS прокси-сервера. Не изучать, не рефакторить, не трогать.

### Key Business Rules

- First free key: 30 days by default, 14 days if referred, 7 days if free quota (`FIRST_MONTH_LIMIT`) is exhausted
- Referral reward: after 5 referrals activate their free period, the referrer gets a free key (`GetFreeLinkViaReferralsService`)
- `MTPRotoKey` stores `token`, `tls_domain`, `node_number`, VDS assignment, and `expired_date`

## Testing Patterns

Tests use `APITestCase` + `factory_boy` factories. VDS HTTP calls are mocked with the `responses` library:

```python
@responses.activate
def test_something(self):
    responses.add(method=responses.POST, url=..., json={...})
```

For tests that trigger `log_service_error` or bot notifications, patch `apps.core.bot.TelegramBot` methods to avoid real Telegram calls.

Factories live in `apps/{app}/tests/factories.py`. All test files are in `apps/{app}/tests/`.
