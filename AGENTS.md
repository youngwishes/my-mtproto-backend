# AGENTS.md

Инструкции для AI-агентов, работающих с BeatVault.

## Контекст проекта

BeatVault — Django backend сервиса подписки на MTProto-прокси. Пользовательское
взаимодействие происходит через Telegram-бота из `bot/`; web UI отсутствует.

Перед изменением соответствующей части системы изучи профильную документацию:

- `docs/BUSINESS.md` — бизнес-правила;
- `docs/ARCHITECTURE.md` — архитектура и инфраструктура;
- `docs/CONTRACTS.md` — API-контракты;
- `docs/MODELS.md` и `docs/apps/` — модели и приложения;
- `docs/DEVELOPMENT_WORKFLOW.md` — обязательный процесс разработки фичи;
- `docs/DEPLOY.md` — production-релиз.

## Обязательный workflow

Разработку новой фичи веди по `docs/DEVELOPMENT_WORKFLOW.md`. Она считается
завершённой только после реализации, зелёных тестов, обновления документации,
commit/push в `main` и разрешённого пользователем deploy с post-deploy проверкой.

Агент может самостоятельно делать commit и push прямо в `main`. Непосредственно
перед production deploy агент обязан остановиться, назвать подготовленный commit
SHA и явно запросить разрешение пользователя. Разрешение нельзя предполагать из
исходной постановки задачи или разрешения на предыдущий deploy.

До deploy агент может подключаться к production по SSH для сбора диагностических
данных. Хост бери только из `ansible/inventory/production.ini`; не дублируй IP в
командах или документации. Диагностика по умолчанию read-only и не разрешает
ручное изменение production.

## Команды

Команды Django выполняются из `src/`. Тесты запускаются из корня:

```bash
make test
make test ARGS="apps.users.tests.test_first_free_link"
make test ARGS="apps.users.tests.test_first_free_link.TestFirstFreeLink.test_first_free_link_30days"
```

Локальный стек:

```bash
docker compose -f docker-compose.local.yml up -d
```

Production разворачивается только по `docs/DEPLOY.md`, через Ansible и после
явного разрешения пользователя. Не используй `docker compose up` как локальную
замену release-процессу.

## Правила реализации

- Пиши тесты до production-кода (TDD), используя существующий `pytest` или
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
  через `responses`, Telegram-вызовы — патчем `apps.core.bot.TelegramBot`.
- При изменении бизнес-логики, контрактов, моделей или архитектуры обновляй
  соответствующие docstrings и документы в `docs/`.
- `apps/music/` — статическая FakeTLS-заглушка. Не изучай, не рефактори и не
  изменяй её без прямого запроса пользователя.

## Архитектурные инварианты

- База данных — source of truth для MTProto-ключей; VDS — равноправные зеркала.
- Issue/reissue выполняет только DB write. Распространение ключа на все healthy
  VDS делает асинхронная reconcile-задача.
- Один `MTPRotoKey` содержит один secret для всей fleet; серверные ссылки
  формируются на лету.
- Кнопка `NotificationTemplate` содержит либо URL, либо callback; URL имеет
  приоритет, а для callback должен существовать aiogram handler.

Детали и актуальные бизнес-правила не дублируй здесь — поддерживай их в `docs/`.
