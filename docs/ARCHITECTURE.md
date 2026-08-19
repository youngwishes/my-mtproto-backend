# Архитектура

Этот документ фиксирует стабильные границы компонентов и потоки данных. Бизнес-
правила находятся в [BUSINESS.md](BUSINESS.md), wire-контракты — в
[CONTRACTS.md](CONTRACTS.md), структура хранения — в [MODELS.md](MODELS.md),
карты конкретных приложений — в [docs/apps/](apps/).

## Место в системе

```text
Telegram user
      │
      ▼
Aiogram bot ──REST──▶ Django backend ──Celery──▶ VDS/VPN fleet
                           │
                           ▼
                        SQLite
```

- `bot/` владеет Telegram-навигацией, текстами экранов и вызовами backend API.
- `src/` владеет авторитетными бизнес-решениями, хранением и внешними provider
  boundaries.
- Celery выполняет доставку, reconcile, уведомления и периодические задачи.
- Redis используется как broker; SQLite остаётся основной БД приложения.

## Стек

| Слой | Технология |
|------|------------|
| Backend | Python 3.13, Django, Django REST Framework |
| Bot | Aiogram |
| Async | Celery, Redis |
| Storage | SQLite, Litestream backup |
| Edge | Nginx, Gunicorn |
| Fleet | telemt и VPN node-agent |
| Packaging | uv, Docker Compose |
| Release | Ansible |

Production Compose stack содержит:

| Service | Ответственность |
|---------|-----------------|
| django | Gunicorn/Django API и migrations entrypoint |
| nginx | TLS termination и reverse proxy |
| redis | Celery broker |
| celery-worker | Фоновые задачи |
| celery-beat | Периодическое расписание |
| flower | Наблюдение за Celery |
| litestream | Репликация SQLite backup |
| bot | Aiogram polling process |

## Публичные домены

Nginx принимает HTTP для `dash.mtprotokeys.com`, `flower.mtprotokeys.com` и
переходного alias `beatvault.ru`. Django обслуживается через dash и alias;
Flower защищён Basic Auth и не направляется в Django.

Сертификат использует lineage `/etc/nginx/ssl/live/beatvault.ru/` с SAN
`beatvault.ru`, `dash.mtprotokeys.com`, `flower.mtprotokeys.com`.
MTProto-секреты используют `TLS_DOMAIN=mtprotokeys.com`, VPN subscription URL —
`VPN_SUBSCRIPTION_BASE_URL=https://dash.mtprotokeys.com`.

Операционные release-команды и проверки принадлежат только
[DEPLOY.md](DEPLOY.md).

## Компоненты репозитория

- `src/apps/core/` — базовые модели, исключения и Telegram transport.
- `src/apps/users/` — пользователь, consent, free period и referrals.
- `src/apps/vds/` — MTProxy-ключи и VDS fleet.
- `src/apps/payments/` — товары, платежи, provider intents, gifts и loyalty.
- `src/apps/vpn/` — VPN-подписки и node delivery.
- `src/apps/notifications/` — шаблоны и рассылки.
- `src/apps/infrastructure/` — операционный инвентарь проектных серверов.
- `bot/` — Telegram presentation layer и typed backend client.
- `ansible/`, `docker-compose*.yml`, `nginx/` — release/runtime infrastructure.

Актуальные модели, сервисы и зависимости каждого приложения перечислены в
[docs/apps/](apps/); архитектурный документ не дублирует дерево файлов.

## Service layer и транзакции

Views, Celery tasks и bot handlers являются transport entrypoints. Они валидируют
вход, вызывают фабрику сервиса и преобразуют DTO/доменные исключения в transport
response. Бизнес-оркестрация находится в сервисах, ORM-запросы — в selectors,
wire parsing — в serializers или provider clients.

Сервис получает зависимости через dataclass-поля; module-level factory отвечает
за wiring. Одна бизнес-операция определяет собственную транзакционную границу.
Внешний HTTP и Telegram transport не удерживают долгую SQLite-транзакцию;
необходимая публикация после commit использует `transaction.on_commit`.

Идемпотентность опирается на сохранённые provider identity/state, уникальные
constraints и условные transitions. Общий distributed lock, event bus или
generic retry framework не вводится без отдельной продуктовой необходимости.

## MTProxy fleet

БД — source of truth для `MTPRotoKey`; VDS являются равноправными зеркалами.
Один ключ содержит один secret для всей fleet, а ссылки формируются на лету для
каждого активного server name.

Issue/reissue меняет только DB state и ставит асинхронную доставку. Fan-out
идемпотентно создаёт пользователя на здоровой VDS либо ротирует secret. После
трёх неудач с интервалами 60/240/960 секунд нода становится unhealthy, а
health-check каждые пять минут пытается вернуть её в fleet. Перед healthy и
backfill он ждёт DB-деактивацию активных истёкших ключей и удаляет с VDS уже
известные БД истёкшие ключи. Ошибка очистки оставляет ноду unhealthy, но не
останавливает обработку остальных серверов.

Точные VDS HTTP methods принадлежат [CONTRACTS.md](CONTRACTS.md#исходящие-запросы-к-vds),
модели — [MODELS.md](MODELS.md#mtprotokey-appsvds).

## Payments и loyalty

Bot получает каталог и доступные способы оплаты из backend. Stars/Yukassa
завершаются синхронным bot-authenticated вызовом; Crypto Pay и Platega создают
локальный intent, принимают provider callback/webhook и завершают тот же
доменный fulfilment асинхронно.

Provider intent сохраняет авторитетный RUB snapshot и state machine. Успешная
выдача продукта, `Payment` и связанные payment-owned snapshots фиксируются в
одной транзакции. Повтор provider identity возвращает сохранённый результат и
не повторяет продуктовый эффект. Telegram success delivery отделена от commit и
имеет собственный marker/reconciliation path.

Apple cashback остаётся частью payments: mutable balance хранится у пользователя,
а purchase/redemption ledgers — в payments. Backend единолично вычисляет status,
quote и confirm; bot передаёт только identifiers/mode и отображает DTO. Полные
правила находятся в [BUSINESS.md](BUSINESS.md#кэшбэк-яблоками), endpoints — в
[CONTRACTS.md](CONTRACTS.md#payments), persistence — в
[MODELS.md](MODELS.md#applecashbackpurchase-appspayments).

Payment provider credentials доступны только Django/Celery environment. Bot не
получает secrets, provider payload или авторитетные суммы/ставки.

## Notifications

`NotificationTemplate` хранит текст и опциональную кнопку. URL имеет приоритет
над callback; для callback presentation layer обязан иметь aiogram handler.
Доменные приложения определяют момент события и контекст, notifications владеет
рендерингом и transport orchestration.

Периодические MTProxy reminders читают ожидаемый expiry и условно отмечают
отправку только для неизменившегося key state, чтобы параллельное продление не
было перезаписано stale marker.

Отдельное infrastructure-напоминание запускается Celery Beat ежедневно в
11:00 UTC. Оно выбирает активные `ProjectServer` с оплатой не позднее
завтрашнего дня и отправляет владельцу одно HTML-safe сообщение, либо ничего,
если список пуст. Задача не изменяет серверы и даты оплаты; при ошибке весь цикл
read/format/send повторяется не более трёх раз с задержкой 30 секунд.

## VPN

VPN является отдельным доменом и не переиспользует MTProxy-модели. Backend
хранит subscription и credentials, публичный token endpoint строит HAPP payload,
а node profiles доставляются асинхронно. Purchase response не ждёт readiness
нод; DB state остаётся авторитетным.

Reissue атомарно ротирует subscription token и protocol credentials, затем
ставит post-commit delivery. Старый token перестаёт обслуживаться сразу после
DB commit, а импортированные профили обновляются eventually.

Пользовательское поведение описано в [BUSINESS.md](BUSINESS.md#vpn), HTTP API —
в [CONTRACTS.md](CONTRACTS.md#vpn), хранение — в
[MODELS.md](MODELS.md#vpnsubscription-appsvpn).

## Аутентификация и секреты

Bot-facing API использует `Bot-Auth-Token`. Публичные provider callbacks имеют
собственную fail-closed проверку secret/signature до доменной обработки.
Provider credentials, Telegram metadata, callback body и payment URL не должны
попадать в пользовательские ошибки или обычные логи.

`RequestLoggingMiddleware` для mutating API пишет только HTTP method и
безопасный path, без headers и body. Секретный сегмент Crypto webhook в path
маскируется; публичный Platega callback обходит middleware logging ещё до чтения
body.

Внутренние VDS/VPN clients используют защищённые настройки backend. Конкретные
headers и payload фиксируются только в [CONTRACTS.md](CONTRACTS.md).

## Release boundary

Production работает как один Docker Compose stack и выпускается Ansible
playbook по точному merged SHA. Миграции запускаются приложением при старте;
откат контейнеров не откатывает уже применённую схему или данные.

Единственная пошаговая release/rollback инструкция находится в
[DEPLOY.md](DEPLOY.md). Процесс разработки, PR, merge и отдельного разрешения на
deploy находится в [DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md).
