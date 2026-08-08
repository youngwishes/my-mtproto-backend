# MTPRoto Keys

MTPRoto Keys — сервис подписки на MTProto-прокси и VPN. Пользователь работает с
сервисом через Telegram-бота; отдельного web UI нет.

## Как устроена система

```text
Telegram user
      │
      ▼
Aiogram bot ──REST──▶ Django backend ──Celery──▶ VDS fleet
                           │                         │
                           ▼                         ▼
                        SQLite                  telemt / VPN
```

- `bot/` отвечает за пользовательские сценарии и обращается к backend API.
- `src/` содержит Django API, бизнес-логику, модели и фоновые задачи.
- Redis используется как брокер Celery.
- VDS-сервисы управляют прокси-ключами и VPN-профилями на удалённых нодах.

Ключевые архитектурные инварианты:

- база данных — источник правды для MTProto-ключей;
- один `MTPRotoKey` содержит один секрет, действующий на всём флоте;
- выдача и перевыпуск изменяют только БД, а доставка на здоровые VDS выполняется
  асинхронно reconcile-задачами;
- Telegram Stars и Crypto Pay включаются глобально через Django admin.

Подробности и границы компонентов описаны в
[архитектурной документации](docs/ARCHITECTURE.md).

## Локальный запуск

Требуются Docker с Compose plugin и настроенные `.env` и `bot/.env`. Backend
переменные перечислены в [.env.example](.env.example), конфигурация бота — в
[bot/README.md](bot/README.md#configuration).

```bash
docker compose -f docker-compose.local.yml up -d
```

Стек поднимает Django, Redis, Celery worker, Celery beat и Telegram-бота. Django
доступен на `http://localhost:8000`.

Для запуска backend без Docker используется Python 3.13 и `uv`:

```bash
uv sync --frozen
cd src
uv run python manage.py migrate
uv run python manage.py runserver 0.0.0.0:8000
```

Бот имеет отдельные зависимости и команды запуска, описанные в
[bot/README.md](bot/README.md).

## Тесты

Backend-тесты запускаются из корня репозитория:

```bash
make test
make test ARGS="apps.users.tests.test_first_free_link"
```

Тесты бота:

```bash
cd bot
uv run pytest
```

End-to-end сценарии требуют локального backend-стека и выделенного тестового VDS;
см. [integration_tests/README.md](integration_tests/README.md).

## Документация

- [BUSINESS.md](docs/BUSINESS.md) — бизнес-правила и пользовательские сценарии.
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — компоненты, взаимодействия и
  инфраструктурные решения.
- [CONTRACTS.md](docs/CONTRACTS.md) — входящие API и исходящие VDS-запросы.
- [MODELS.md](docs/MODELS.md) — модели данных и их инварианты.
- [docs/apps/](docs/apps/) — ответственность отдельных Django-приложений.
- [DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md) — процесс разработки и
  выпуска изменений.
- [DEPLOY.md](docs/DEPLOY.md) — production release через Ansible, rollback и
  post-deploy проверки.

Production разворачивается только по [DEPLOY.md](docs/DEPLOY.md). Локальная
команда Docker Compose не заменяет release-процесс.
