# BeatVault — MTProto Proxy Subscription Service

## Что это

BeatVault — сервис продажи MTProto proxy ссылок для пользователей Telegram в странах, где мессенджер замедлен или заблокирован. Весь пользовательский опыт построен через Telegram-бота: пользователь пишет боту, получает прокси-ссылку, нажимает — Telegram начинает работать быстро.

## Архитектура системы

```
┌──────────────┐     ┌─────────────────┐     ┌───────────────────┐     ┌─────────────────────┐
│   Telegram   │────>│   Aiogram Bot   │────>│  Django Backend   │────>│  VDS Instance (N)   │
│   User       │<────│   (polling)     │<────│  (DRF API)        │<────│  (FastAPI + telemt)  │
└──────────────┘     └─────────────────┘     └───────────────────┘     └─────────────────────┘
                                                     │
                                              ┌──────┴───────┐
                                              │ Celery + Redis│
                                              │ (фоновые     │
                                              │  задачи)     │
                                              └──────────────┘
```

**Telegram Bot** (`bot/`) — Aiogram 3.x, polling-режим. Принимает команды от пользователя, рисует inline-кнопки, обрабатывает платежи. Общается с бэкендом через REST API с заголовком `Bot-Auth-Token`.

**Django Backend** (`src/`) — Django 6 + DRF. "Мозг" системы: бизнес-логика, управление ключами, платежи, реферальная программа, уведомления. БД — SQLite. Фоновые задачи через Celery + Redis.

**VDS Instance** (`../my-mtproto-vds-instance/`) — FastAPI-сервис, развёрнутый на каждом VDS-сервере. "Рабочая лошадка": принимает команды от Django и управляет прокси-сервером telemt (добавляет/удаляет пользователей). Два режима работы:
- **V1**: прямая запись в TOML-конфиг telemt
- **V2**: HTTP-запросы к management API telemt на порту 9091

**telemt** — сам MTProto-прокси (Docker-образ `ghcr.io/telemt/telemt`). Слушает порт 443, маскируется под TLS-трафик к `beatvault.ru`. Каждый пользователь получает уникальный секрет, лимит — 3 одновременных IP-адреса.

## Ключевые бизнес-потоки

### Бесплатная ссылка (первый визит)

```
/start → CheckFirstFreeLinkService → определяет период:
  - 30 дней (обычный пользователь)
  - 14 дней (пришёл по реферальной ссылке)
  - 7 дней (лимит FIRST_MONTH_LIMIT=50 исчерпан)
→ IssueKeyService → VDS с наименьшей нагрузкой
→ POST /api/v2/users/add {username, secret}
→ MTPRotoKey сохраняется в БД
→ Бот отправляет tg://proxy ссылку
```

Пользователь нажимает ссылку — Telegram подключается к прокси. Одна ссылка работает на 3 устройствах одновременно.

### Покупка ссылки (79 RUB / 60 Stars)

Три платёжных провайдера:

| Провайдер | Механизм | Endpoint |
|-----------|----------|----------|
| YuKassa (Yandex) | Telegram Payments API | Бот обрабатывает `successful_payment` → `POST /api/buy/` |
| Telegram Stars | Встроенная валюта Telegram | Аналогичный флоу через бота |
| Tribute | Webhook с HMAC-подписью | `POST /api/webhook/` напрямую на бэкенд |

При покупке: если у пользователя есть активный ключ — продлевается на 30 дней. Если нет — генерируется новый.

### Реферальная программа

```
Пользователь делится ссылкой https://t.me/bot/?start=<username>
→ Приглашённый регистрируется, активирует бесплатный период
→ referral_activated = True
→ После 5 активированных рефералов → можно забрать бесплатную 14-дневную ссылку
→ Лимит: 1 бесплатная ссылка через рефералов (REFERRAL_LINKS_LIMIT=1)
```

### Жизненный цикл ключа (Celery Beat)

| Время (UTC) | Задача | Действие |
|-------------|--------|----------|
| 15:00 | `notify_before_removing_daily` | Предупреждение за 1 день до истечения |
| 08:00 | `notify_before_removing_daily_hour_before` | Предупреждение за 1 час |
| 09:00 | `remove_user_keys_daily` | Удаление истёкших ключей с VDS, деактивация в БД |

Пользователь может перевыпустить ключ вручную (кнопка "Перевыпустить ссылку"), кулдаун — 5 минут. При перевыпуске генерируется новый секрет, старый удаляется со всех VDS.

## Инфраструктура VDS

Несколько VDS-серверов, каждый с экземпляром telemt + FastAPI. Новые ключи назначаются на наименее нагруженный сервер (`get_least_populated()`). При создании ключа он реплицируется на остальные серверы через Celery-задачу — пользователь может подключиться через любой узел.

```
Django → POST /api/v2/users/add → VDS #1 (primary, least populated)
                                     ↓ (async Celery task)
                                  VDS #2, #3, ... (replicas)
```

Каждый VDS-сервер:
- telemt на порту 443 (прокси)
- telemt management API на порту 9091
- FastAPI на порту 8000 (интерфейс для Django)
- Лимит: `user_limit` (по умолчанию 200) пользователей на сервер

Есть admin action для миграции всех ключей с упавшего сервера на другие.

## Модели данных

### SystemUser (apps/users)
Расширяет `AbstractUser`. Ключевые поля:
- `telegram_username` — идентификатор пользователя
- `first_month_free_used` — использовал ли бесплатный период
- `invited_from_username` — кто пригласил (реферал)
- `referral_activated` — активировал ли свой бесплатный период (для подсчёта рефералов пригласившего)
- `referral_link_activated_count` — сколько раз забирал бесплатную реферальную ссылку

### VDSInstance (apps/vds)
Прокси-сервер. Поля: `name`, `number`, `ip_address`, `internal_ip_address`, `port`, `user_limit`. Метод `is_available()` проверяет, что лимит не исчерпан.

### MTPRotoKey (apps/vds)
Прокси-ключ пользователя. Ключевые поля:
- `token` — секрет для подключения
- `vds` → VDSInstance
- `user` → SystemUser
- `expired_date` — дата истечения
- `tls_domain`, `node_number` — для формирования ссылки `tg://proxy?server={node}.beatvault.ru&port=443&secret=ee{token}{hex(domain)}`
- `was_deleted`, `is_active` — статус
- `is_winner` — победитель конкурса (безлимитный ключ)

### Product (apps/payments)
Товар: `price` (79 RUB), `stars_price` (60 Stars), `provider_data` (JSON для YuKassa).

### Payment (apps/payments)
Запись об оплате: `charge_id`, `provider` (YUKASSA/STARS), связь с `user` и `key`.

### TributeDigitalPayment (apps/tribute)
Webhook-платёж от Tribute: `amount`, `currency`, `telegram_user_id`, `is_success`.

## API Endpoints

Все endpoints (кроме Tribute webhook) защищены заголовком `Bot-Auth-Token`.

| Endpoint | Метод | Назначение |
|----------|-------|------------|
| `/api/first-free-link/` | POST | Выдать бесплатный ключ |
| `/api/check-first-free-link/` | POST | Проверить доступность бесплатного периода |
| `/api/referral/cabinet/` | POST | Статистика рефералов |
| `/api/referral/link/` | POST | Забрать реферальную ссылку |
| `/api/update-link/` | POST | Перевыпустить ключ |
| `/api/check-agreement/` | POST | Согласие победителя конкурса |
| `/api/` | GET | Получить товар (Product) |
| `/api/buy/` | POST | Зафиксировать оплату |
| `/api/webhook/` | POST | Tribute webhook (HMAC-подпись) |

## Стек

| Компонент | Технология |
|-----------|------------|
| Backend | Django 6.0.2, DRF 3.16.1, Python 3.13 |
| Bot | Aiogram 3.x (polling) |
| VDS API | FastAPI 0.131, Uvicorn |
| Прокси | telemt (Docker-образ) |
| Очередь задач | Celery 5.6.2 + Redis 7 |
| Мониторинг Celery | Flower |
| Reverse proxy | Nginx (SSL termination) |
| БД | SQLite |
| Деплой | Docker Compose |

## Docker Compose (production)

| Сервис | Назначение | Порт |
|--------|------------|------|
| django | Django + Gunicorn | 8000 |
| nginx | Reverse proxy + SSL | 80, 443 |
| redis | Брокер Celery | 6379 |
| celery-worker | Обработка задач | — |
| celery-beat | Расписание задач | — |
| flower | Мониторинг Celery | 5555 |
| bot | Telegram-бот | — |

На каждом VDS-сервере отдельный docker-compose с telemt + FastAPI.

## Команды разработки

```bash
cd src

python manage.py runserver 0.0.0.0:8000    # dev-сервер
python manage.py test                       # все тесты
python manage.py test apps.vds.tests        # тесты одного app
python manage.py migrate                    # миграции

# Docker
docker-compose -f docker-compose.yml up -d          # production
docker-compose -f docker-compose.local.yml up -d     # local
```

## Структура проекта

```
my-mtproto-backend/
├── src/
│   ├── config/                  # Django settings (base, bot, celery, vds, referrals, tribute)
│   ├── apps/
│   │   ├── core/                # BaseError, TelegramBot, middleware
│   │   ├── users/               # SystemUser, бесплатные ссылки, рефералы
│   │   ├── vds/                 # VDSInstance, MTPRotoKey, инфра-сервисы, Celery-задачи
│   │   ├── payments/            # Product, Payment, YuKassa/Stars
│   │   ├── tribute/             # TributeDigitalPayment, webhook
│   │   └── music/               # (пустое приложение)
│   └── manage.py
├── bot/
│   └── src/
│       ├── bot.py               # Инициализация Aiogram
│       ├── handlers.py          # /start, оплата, рефералы, кнопки
│       ├── config.py            # Переменные окружения
│       ├── services/            # HTTP-клиенты к Django API
│       └── keyboards/           # Inline-клавиатуры
├── nginx/                       # Конфиг Nginx
├── docker-compose.yml           # Production
├── docker-compose.local.yml     # Local dev
├── Dockerfile                   # Django image
└── requirements.txt

my-mtproto-vds-instance/         # Отдельный репозиторий, на каждом VDS
├── src/
│   ├── app.py                   # FastAPI, подготовка TOML при старте
│   ├── config.py                # Переменные окружения
│   ├── api/routes/
│   │   ├── v1/users.py          # Прямая запись в TOML
│   │   └── v2/users.py          # Через HTTP API telemt
│   ├── services/
│   │   ├── v1/                  # AddUserServiceV1, RemoveUserServiceV1
│   │   └── v2/                  # AddUserServiceV2, RemoveUserServiceV2
│   └── tests/
├── telemt/telemt.toml           # Конфиг прокси-сервера
├── docker-compose.yaml          # telemt + FastAPI
└── Dockerfile
```
