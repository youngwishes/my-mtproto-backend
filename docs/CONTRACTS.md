# Контракты API

Базовый путь: `/api/v1`

Все эндпоинты защищены заголовком `Bot-Auth-Token`.

---

## Users

### POST /users/consent/status/

Read-only проверяет единое юридическое согласие. Отсутствующий пользователь
возвращает `false` и не создаётся.

```json
{"username": "1487189460"}
```

```json
{"legal_terms_accepted": false}
```

---

### POST /users/consent/accept/

Создаёт пользователя только после явного принятия или идемпотентно подтверждает
согласие существующего пользователя. Повторный вызов не меняет сохранённого
referrer.

```json
{
  "username": "1487189460",
  "telegram_username": "john_doe",
  "invited_from_username": "9876543210"
}
```

```json
{"legal_terms_accepted": true}
```

Оба endpoint защищены `Bot-Auth-Token`.

---

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
  "expired_date": "06.07.26"
}
```

Ссылка не возвращается: ключ валиден на всём флоте, бот показывает кнопку «📡 Мои серверы». Доставка секрета на серверы — асинхронная (Celery).

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
| `telegram_username` | string? | Username в Telegram; необязательное, если у юзера нет @username — поле опускается |
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
  "expired_date": "20.06.26"
}
```

**Ошибки:** `NotEnoughReferrals`, `AlreadyUsedProgram`.

---

### POST /users/update-link/

Перевыпуск ключа: генерируется новый секрет, старый перестаёт работать. Запись обновляется в БД, новый секрет асинхронно доставляется на все здоровые VDS. Кулдаун — 5 минут.

**Запрос:**

```json
{
  "username": "1487189460"
}
```

**Ответ:** `200 OK`

```json
{
  "expired_date": "06.07.26"
}
```

Ссылка не возвращается — бот показывает кнопку «📡 Мои серверы».

**Ошибки:** `KeyDoesNotExist`, `TooManyRequests` (чаще 1 раза в 5 минут).

---

### POST /users/my-servers/

Возвращает информацию о текущем ключе пользователя и списке серверов.

Если активного ключа нет, а бесплатный период ещё **не использован** (включая
нового пользователя) — период активируется на лету (логика `FirstFreeLinkService`:
30/14/7 дней + реферальный бонус), и сразу возвращается список серверов. Если
период уже израсходован, а активного ключа нет — `KeyDoesNotExist`.

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

**Ошибки:** `KeyDoesNotExist` (нет активного ключа и бесплатный период уже израсходован).

---

## Payments

`GET /payments/products/vpn_30d/` возвращает активный VPN-товар в том же
формате, что и legacy `GET /payments/`; legacy route остаётся MTProto alias.

### POST /api/v1/payments/crypto/invoices/

Защищён `Bot-Auth-Token`. Принимает `username` (Telegram ID) и `purchase_kind`
(`subscription`, `vpn_subscription` или `gift_certificate`). Создаёт 30-минутный
Crypto Pay-счёт или возвращает существующий активный счёт этого инициатора и
вида покупки.

Успешный ответ — `200 OK` с ровно четырьмя полями:

```json
{
  "invoice_url": "https://pay.crypt.bot/…",
  "rub_amount": "99.00",
  "expires_at": "2026-08-31T12:00:00Z",
  "reused": false
}
```

`reused` равен `true` только для уже активного счёта. Одновременное создание
возвращает `409`, недоступность провайдера — `503`; ошибки входных данных следуют
стандартному DRF `400`. Сумма сохраняется decimal-строкой, без float.

### POST /api/v1/payments/crypto/webhooks/<secret>/

Публичный endpoint принимает только `invoice_paid`. URL secret должен совпасть
с backend-настройкой, иначе ответ `404`. Затем проверяется заголовок
`crypto-pay-api-signature`: отсутствующая или неверная HMAC-SHA256 подпись даёт
`401`. Некорректный JSON, payload или `update_type` дают `400`.

Подписанный корректный webhook, включая повтор уже выполненной покупки и
несогласованный/неизвестный счёт, отвечает `200`; во втором случае выдача не
выполняется и создаётся безопасный admin warning. Временная ошибка БД, выдачи
или постановки warning возвращает `503`, чтобы провайдер или reconciliation мог
повторить обработку. Webhook не принимает Bot-Auth-Token и не логирует body,
signature или секреты.

---

## VPN

### GET /vpn/menu/?username=<telegram_id>

Защищён `Bot-Auth-Token`; выполняет только read-only поиск и возвращает ровно:

```json
{
  "status": "none|active|expired",
  "expired_at": "ISO-8601 or null",
  "subscription_url": "absolute URL or null"
}
```

У `none` оба nullable-поля равны `null`; у `expired` URL сохраняется, но не
выдаёт рабочую конфигурацию.

### GET /api/v1/vpn/subscriptions/<token>/

Публичный endpoint. Успешный ответ имеет `200 OK`, `Content-Type: text/plain` и
`profile-title: mtprotokeys.ru`; новый заголовок не изменяет существующие
subscription URL или Base64 payload.

### POST /vpn/payments/buy/

Защищён `Bot-Auth-Token`. Фиксирует только VPN-платёж и принимает:

```json
{
  "username": "1487189460",
  "charge_id": "vpn_charge_001",
  "provider": "stars",
  "product_code": "vpn_30d"
}
```

Ответ содержит срок и постоянную внешнюю subscription-ссылку:

```json
{
  "expired_at": "2026-08-31T12:00:00+00:00",
  "subscription_url": "https://example.com/api/v1/vpn/subscriptions/token/"
}
```

---

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
  "stars_price": 99
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

### POST /payments/gift-certificates/buy/

Фиксирует успешную оплату подарочного сертификата. Создаёт одноразовый код на
30 дней подписки и не продлевает подписку покупателя. Повторная обработка того
же платежа возвращает уже созданный код и не создаёт второй сертификат.

**Запрос:**

```json
{
  "username": "1487189460",
  "charge_id": "yukassa_gift_001",
  "provider": "yukassa"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `username` | string | Telegram ID покупателя |
| `charge_id` | string | Идентификатор платежа от провайдера |
| `provider` | string | `"yukassa"` или `"stars"` |

**Ответ:** `200 OK`

```json
{
  "code": "KEY-ABCD-1234"
}
```

### POST /payments/gift-certificates/activate/

Активирует подарочный сертификат. Если у пользователя есть активный ключ —
продлевает его на 30 дней; если нет — выдаёт новый ключ на 30 дней. Активация
не влияет на бесплатный период и реферальную программу.

**Запрос:**

```json
{
  "username": "1487189460",
  "code": "KEY-ABCD-1234"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `username` | string | Telegram ID получателя |
| `code` | string | Код сертификата формата `KEY-XXXX-XXXX` |

**Ответ:** `200 OK`

```json
{
  "expired_date": "06.08.26"
}
```

**Ошибки:** `GiftCertificateNotFound`, `GiftCertificateAlreadyActivated`, `GiftCertificateExpired`.

---

## Исходящие запросы к VDS

Бэкенд общается с FastAPI-сервисами на VDS через HTTP. Выдача/перевыпуск ключа — это запись в БД + Celery-таск `push_key_to_servers_task`, который фан-аутит секрет на **все здоровые** VDS. Доставка идемпотентна и поддерживает ротацию: POST `/api/users`; если пользователь уже есть (`409`) — секрет ротируется через PATCH (новый перевыпущенный токен замещает старый; PATCH тем же секретом — безопасный no-op).

| Действие | Метод | URL | Тело |
|----------|-------|-----|------|
| Доставить ключ (POST, на `409` → PATCH-ротация) | POST/PATCH | `{server.internal_url}/api/users` | `{username, secret}` |
| Удалить | DELETE | `{server.internal_url}/api/users` | `{usernames: [...]}` |

Таймаут: `VDS_REQUEST_TIMEOUT` секунд. При исчерпании ретраев сервер помечается `is_healthy=False`; восстановление и бэкфилл ключей — через health-check + `sync_keys_to_vds_task`.
