# Интеграционные тесты (бот → бэкенд → VDS)

Чёрнобоксовый e2e-слой: реальные domain-клиенты бота (`bot/src/domains/*`) →
живой Django-бэкенд → Celery (`push_key_to_servers_task`) → живой VDS-инстанс
(telemt-api). Проверяется не только HTTP-ответ, но и **фактическое состояние
секрета на всех VDS** (через `GET /api/users/{username}`).

> ⚠️ ТОЛЬКО против локального/стейдж-стека с тестовой БД. В прод (~1500 живых
> пользователей) — НЕЛЬЗЯ. Тестовые пользователи — синтетические telegram_id
> с префиксом `999…`, харнесс чистит за собой (БД + DELETE на VDS).

## Архитектура (вариант A — общий ORM)

- Django поднимается прямо в харнессе (`integration_tests/settings.py`), деля
  **тот же sqlite**, что и контейнеры: `<repo>/data/db.sqlite3`.
- `arrange`/`assert` состояния бэкенда — через ORM (`db.py`).
- `act` — через реальные async domain-клиенты бота (`helpers.make_clients()`).
- `verify` на VDS — через `GET/DELETE /api/users` (`helpers.py`).

## Предусловия

1. Поднят backend-стек: `docker-compose -f docker-compose.local.yml up -d django redis celery-worker`.
2. Поднят локальный VDS (`../my-mtproto-vds-instance`, telemt-api на `:8080`).
3. В БД есть здоровый `VDSInstance`, чей `internal_ip_address:port` достижим из
   celery-контейнера (по умолчанию `host.docker.internal:8080`) — создаётся
   `db.ensure_local_vds()` в `arrange`.

## Запуск

```bash
# из репо-корня, venv с backend + bot зависимостями + pytest-asyncio
.venv-integration/bin/pytest integration_tests -v
```

## Конфиг (env, см. `config.py`)

| env | дефолт | назначение |
|---|---|---|
| `INTEG_BACKEND_URL` | `http://localhost:8000` | живой Django |
| `INTEG_VDS_VERIFY_URLS` | `http://localhost:8080` | хост-достижимые VDS (GET/DELETE) |
| `INTEG_VDS_INTERNAL_IP` | `host.docker.internal` | как celery видит VDS |
| `INTEG_VDS_PORT` | `8080` | порт VDS |
