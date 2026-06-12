# Контракты API

Базовый путь: `/api/v1`

Все эндпоинты защищены заголовком `Bot-Auth-Token`.

---

## Users

### POST /users/first-free-link/

Выдаёт бесплатный ключ новому пользователю.

**Запрос:**

```json
{
  "username": "1487189460"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `username` | string | Telegram ID пользователя |

**Ответ:** `200 OK`

```json
{
  "expired_date": "2026-07-06T09:00:00Z",
  "link": "tg://proxy?server=space.beatvault.ru&port=443&secret=ee..."
}
```

**Ошибки:** `AlreadyUsedFree` — пользователь уже использовал бесплатный период.

---

### POST /users/check-first-free-link/

Проверяет доступность бесплатного периода и определяет его длительность.

**Запрос:**

```json
{
  "username": "1487189460",
  "telegram_username": "john_doe",
  "invited_from_username": "9876543210"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `username` | string | Telegram ID |
| `telegram_username` | string | Username в Telegram |
| `invited_from_username` | string? | Telegram ID пригласившего |

**Ответ:** `200 OK`

```json
{
  "available_free_period": "MONTH"
}
```

Возможные значения: `MONTH` (30 дней), `TWO_WEEK` (14 дней), `WEEK` (7 дней), `NOT_AVAILABLE`.

---

### POST /users/referral/cabinet/

Статистика реферальной программы пользователя.

**Запрос:**

```json
{
  "username": "1487189460"
}
```

**Ответ:** `200 OK`

```json
{
  "total_referrals_count": 12,
  "active_referrals_count": 7,
  "referral_link": "https://t.me/bot/?start=1487189460",
  "link_activated_count": 1
}
```

---

### POST /users/referral/link/

Забирает бесплатную реферальную ссылку (требуется минимум 5 активных рефералов).

**Запрос:**

```json
{
  "username": "1487189460"
}
```

**Ответ:** `200 OK`

```json
{
  "expired_date": "2026-06-20T09:00:00Z",
  "link": "tg://proxy?server=space.beatvault.ru&port=443&secret=ee..."
}
```

**Ошибки:** `NotEnoughReferrals`, `AlreadyUsedProgram`.

---

### POST /users/update-link/

Перевыпуск ключа. Старый ключ перестаёт работать. Кулдаун — 5 минут.

**Запрос:**

```json
{
  "username": "1487189460"
}
```

**Ответ:** `200 OK`

```json
{
  "link": "tg://proxy?server=space.beatvault.ru&port=443&secret=ee...",
  "expired_date": "2026-07-06T09:00:00Z"
}
```

**Ошибки:** `KeyDoesNotExist`, `TooManyRequests` (чаще 1 раза в 5 минут), `NoVDSAvailable` (нет доступных серверов).

---

### POST /users/my-servers/

Возвращает информацию о текущем ключе пользователя и списке серверов.

**Запрос:**

```json
{
  "username": "1487189460"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `username` | string | Telegram ID пользователя |

**Ответ:** `200 OK`

```json
{
  "expired_date": "11.07.26",
  "servers": [
    {
      "location": "🇳🇱 Нидерланды",
      "proxy_link": "tg://proxy?server=space.beatvault.ru&port=443&secret=ee..."
    }
  ]
}
```

**Ошибки:** `KeyDoesNotExist` (пользователь не имеет активного ключа).

---

## Payments

### GET /payments/

Возвращает данные о товаре для формирования Telegram-инвойса.

**Ответ:** `200 OK`

```json
{
  "title": "MTPRoto Proxy — 30 дней",
  "description": "Прокси-ссылка на 30 дней для Telegram",
  "currency": "RUB",
  "provider_data": "{\"receipt\": ...}",
  "send_email_to_provider": true,
  "need_email": true,
  "price": 99.00,
  "stars_price": 80
}
```

---

### POST /payments/buy/

Фиксирует успешный платёж. Продлевает существующий ключ или выдаёт новый.

**Запрос:**

```json
{
  "username": "1487189460",
  "charge_id": "yukassa_charge_001",
  "provider": "yukassa"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `username` | string | Telegram ID |
| `charge_id` | string | Идентификатор платежа от провайдера |
| `provider` | string | `"yukassa"` или `"stars"` |

**Ответ:** `200 OK` (без тела)

---

## Исходящие запросы к VDS

Бэкенд общается с FastAPI-сервисами на VDS через HTTP:

| Действие | Метод | URL | Тело |
|----------|-------|-----|------|
| Создать ключ | POST | `{vds.internal_url}/api/users` | `{username, secret}` |
| Перевыпустить | PATCH | `{vds.internal_url}/api/users` | `{username, secret}` |
| Удалить | DELETE | `{vds.internal_url}/api/users` | `{usernames: [...]}` |

Таймаут: `VDS_REQUEST_TIMEOUT` секунд.
