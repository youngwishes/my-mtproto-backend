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

## Компоненты репозитория

- `src/config/` — настройки Django, маршрутизация, Celery и WSGI entrypoint.
- `src/apps/` — доменные и инфраструктурные Django-приложения. Их зоны
  ответственности перечислены в [docs/apps/](apps/).
- `bot/` — отдельное Aiogram-приложение со своим dependency graph и тестами;
  актуальная структура и команды находятся в [bot/README.md](../bot/README.md).
- `integration_tests/` — end-to-end сценарии bot → backend → VDS; требования к
  окружению описаны в
  [integration_tests/README.md](../integration_tests/README.md).
- `ansible/`, Compose- и Nginx-конфигурация — инфраструктура локального запуска и
  production release. Канонический процесс выпуска описан в
  [DEPLOY.md](DEPLOY.md).

Документ фиксирует границы и взаимодействия компонентов, но намеренно не
дублирует дерево файлов: актуальный состав модулей определяется репозиторием и
профильной документацией приложений.

## apps/core — Инфраструктурное ядро

`apps.core` содержит базовые модели, доменные и инфраструктурные исключения,
декораторы обработки ошибок и Telegram-транспорт. Публичные обязанности и
зависимости приложения перечислены в [apps/CORE.md](apps/CORE.md).

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

## Crypto Pay

Django владеет созданием Crypto Pay-счёта и webhook; bot получает только
четырёхпольный ответ защищённого `Bot-Auth-Token` API и не получает token или
webhook secret. Локальный `CryptoPaymentIntent` хранит состояние покупки,
публичный UUID payload и provider invoice. Вызов провайдера выполняется вне
долгой SQLite-транзакции, а выдача использует conditional transitions и
частичные unique constraints, поэтому повторный webhook или reconciliation не
выдают продукт повторно. После commit отдельная Celery-задача доставляет
результат пользователю.

Webhook проверяет и secret path, и HMAC от raw body. До выдачи сверяются счёт,
RUB-сумма, валюта, paid status и разрешённый/оплаченный asset; безопасные
идентификаторы и reason code достаточны для warning. Token, signature, raw body,
PII и URL результата в логи не попадают. Celery Beat запускает reconciliation
`*/10`, чтобы повторно обработать оплаченные незавершённые покупки и отдельно
доставить пропущенные уведомления.

## Доступность способов оплаты

`PaymentMethod` в `apps.payments` хранит единственный глобальный флаг
`is_active` для каждого поддержанного кодом способа (`stars`, `crypto_pay`).
Модель не связана с `Product`: один переключатель в Django admin действует для
MTProto, VPN и подарочного сертификата. Admin разрешает менять только
`is_active`; добавление, удаление и переименование способов отключены.

При каждом `GET /api/v1/payments/` или
`GET /api/v1/payments/products/<code>/` selector читает активные строки из БД
без кеша, отбрасывает неизвестные коды и возвращает `payment_methods` в
фиксированном порядке Stars → Crypto Pay. Бот получает список вместе с уже
нужными данными товара и строит соответствующую клавиатуру. Пустой список —
штатное состояние: экран содержит `Оплата временно недоступна` и текущую кнопку
«Назад». Ошибки product API не маскируются под это состояние, а обработчики уже
показанных платёжных кнопок не перечитывают активность.

Миграция создаёт Stars и Crypto Pay активными, поэтому rollout совместим со
старым ботом: сначала разворачиваются migration/backend с аддитивным API-полем,
затем bot. Операционный rollback выполняется в обратном порядке без удаления
таблицы и сохранённого admin-состояния.

### Ежедневная выдача бесплатных периодов

Celery Beat в 12:00 UTC вызывает тонкую задачу
`apps.users.tasks.grant_daily_free_trials_task`. Selector в `apps.users` выбирает
не активировавших пробный период пользователей по `date_joined, pk` (`date_joined`
является timestamp создания у `SystemUser`, наследуемым от `AbstractUser`).
`DailyFreeTrialGrantService` получает selector, сервис выдачи, selectors ключа и
активных VDS и Telegram transport через DI. Он продолжает обход после ошибки до
десяти сохранённых активаций, после чего отправляет один итоговый отчёт админу.

`FirstFreeLinkService` блокирует строку пользователя через `select_for_update()`
и повторно проверяет `first_month_free_used` внутри транзакции. Поэтому
параллельный или повторный запуск не может выдать одному пользователю два
бесплатных периода. Выдача остаётся DB-only; доставка секрета на healthy VDS
выполняется существующей reconcile-задачей.

## apps/notifications — Уведомления и рассылки

`apps.notifications` хранит шаблоны сообщений и рассылок, выбирает получателей,
разрешает контекст и ставит отправку в Celery. Обзор моделей, сервисов и
зависимостей находится в [apps/NOTIFICATIONS.md](apps/NOTIFICATIONS.md).

`NotificationTemplate` хранит HTML-текст с `{переменными}`, опциональную кнопку и флаг `include_payment_buttons` (добавляет кнопку «⚡Продлить» с `callback_data="boost_paid"`). Кнопка может быть URL (`button_url`) или callback (`button_callback_data`) — URL имеет приоритет.

`Mailing` отслеживает статусы: DRAFT → SENDING → COMPLETED / PARTIALLY_COMPLETED / FAILED. Поля `sent_count` и `failed_count` фиксируют результаты рассылки.

## Аутентификация

Все API-эндпоинты защищены заголовком `Bot-Auth-Token`, проверяемым через permission `BotAuthToken` против `settings.BOT_AUTH_TOKEN`.

## VPN

`apps.vpn` хранит единственную VPN-подписку пользователя, стабильные credentials
и subscription token. Бот запрашивает read-only menu endpoint, получает цены
только из активного `Product(code="vpn_30d")`, а successful payment направляет
исключительно в `/api/v1/vpn/payments/buy/`. Ответ покупки содержит срок и
внешнюю постоянную subscription URL; бот показывает её сразу и не ждёт фоновой
выдачи профилей на VPN-ноды.

VPN callbacks и invoice payload отделены от MTProto: `vpn`,
`vpn_pay_yukassa`/`vpn_pay_stars` и `vpn_yukassa`/`vpn_stars`. Статусы меню
`none`, `active`, `expired` формирует backend; бот ветвится только по этому
полю. Уведомления VPN ведут в callback `vpn`.

## Деплой

Docker Compose с 8 сервисами:

| Сервис | Назначение | Порт |
|--------|------------|------|
| django | Django + Gunicorn | 8000 |
| nginx | Reverse proxy + SSL | 80, 443 |
| redis | Брокер Celery | 6379 |
| celery-worker | Обработка задач | — |
| celery-beat | Расписание задач | — |
| flower | Мониторинг Celery | 5555 |
| litestream | Репликация SQLite в S3 | — |
| bot | Telegram-бот | — |

Все сервисы в общей bridge-сети `backend`.
