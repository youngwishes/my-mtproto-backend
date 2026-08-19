# AGENTS.md

Инструкции для AI-агентов, работающих с MTPRoto Keys.

## Контекст и навигация

MTPRoto Keys — Django backend подписки на MTProto-прокси и VPN. Пользователь
работает через Telegram-бота из `bot/`; отдельного web UI нет.

Перед изменением соответствующей части системы изучи документ-владелец:

- [BUSINESS.md](docs/BUSINESS.md) — пользовательские сценарии и бизнес-правила;
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — границы компонентов и инфраструктура;
- [CONTRACTS.md](docs/CONTRACTS.md) — входящие и исходящие API-контракты;
- [MODELS.md](docs/MODELS.md) — структура хранения и DB-инварианты;
- [docs/apps/](docs/apps/) — компактные карты приложений;
- [DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md) — разработка, ревью,
  публикация и permission boundaries;
- [DEPLOY.md](docs/DEPLOY.md) — единственная release-инструкция и production
  smoke checks.

Полный процесс выполняй по `DEVELOPMENT_WORKFLOW.md`. Не пушь напрямую в
`main`, не выполняй merge или production deploy без требуемого отдельного
разрешения пользователя. Worktree в этом репозитории не создавай: работай в
текущем checkout через feature-ветку `codex/<feature-slug>`.

## Команды

Команды Django выполняются из `src/`. Backend-тесты запускаются из корня:

```bash
make test
make test ARGS="apps.users.tests.test_first_free_link"
make test ARGS="apps.users.tests.test_first_free_link.TestFirstFreeLink.test_first_free_link_30days"
```

Полная проверка документационных границ:

```bash
make docs-check
```

Локальный стек:

```bash
docker compose -f docker-compose.local.yml up -d
```

Production выпускается только по `DEPLOY.md`. Локальный `docker compose up` не
заменяет release-процесс.

## Правила реализации

- Пиши тесты до production-кода, используя существующий `pytest` или
  `unittest`; новый test framework не добавляй.
- Сервисы — `@final` frozen dataclass с `kw_only=True`, `slots=True` и
  `frozen=True`, реализующий `__call__` с keyword-only аргументами.
- Зависимости сервисов инъектируй через поля dataclass. Создание зависимых
  сервисов внутри `__call__` запрещено; wiring выполняют module-level factory
  functions.
- ORM-запросы переиспользуй или добавляй в `selectors.py`, не размещай их в
  сервисах.
- Доменные исключения хранятся в `exceptions.py`, enum — в `enums.py`; между
  слоями передавай DTO.
- Используй `from __future__ import annotations`. Импорты только для аннотаций
  помещай под `TYPE_CHECKING`.
- Каждый пакет явно реэкспортирует public symbols из `__init__.py`; star imports
  запрещены.
- Новые модели наследуй от `BaseDjangoModel`. Не дублируй `is_active`,
  `created_at`, `updated_at`; используй `Model.objects.active()` вместо
  `filter(is_active=True)`.
- `BaseServiceError` и `BaseInfraError` принимают `telegram_id` первым
  аргументом; docstring исключения является сообщением пользователю.
- API-тесты передают заголовок `Bot-Auth-Token`. Внешние VDS HTTP-вызовы мокай
  через `responses`. Telegram-вызовы мокай в модуле-потребителе: патчь
  импортированный туда `send_telegram_message`; транспорт находится в
  `apps.core.telegram.transport`.
- Изменение бизнес-правила, контракта, модели или архитектурной границы обновляет
  только соответствующий документ-владелец. Перед публикацией запускай
  `make docs-check`.
- `src/apps/music/` — статическая FakeTLS-заглушка. Не изучай, не рефактори и не
  изменяй её без прямого запроса пользователя.

## Архитектурные инварианты

- База данных — source of truth для MTProto-ключей; VDS — равноправные зеркала.
- Issue/reissue выполняет только DB write. Распространение ключа на healthy VDS
  делает асинхронная reconcile-задача.
- Один `MTPRotoKey` содержит один secret для всей fleet; серверные ссылки
  формируются на лету.
- Кнопка `NotificationTemplate` содержит URL либо callback; URL имеет приоритет,
  а для callback должен существовать aiogram handler.

Не дублируй здесь процесс разработки и актуальные продуктовые детали: следуй
ссылкам на канонические документы выше.
