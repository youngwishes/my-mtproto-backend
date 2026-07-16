# Контракты API

Базовый путь: `/api/v1`

Все эндпоинты защищены заголовком `Bot-Auth-Token`, кроме явно отмеченной
публичной subscription URL.

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

## VPN bot API

Все endpoints этого раздела принимают только `POST` и требуют
`Bot-Auth-Token`. Денежная сумма передаётся целым числом в минимальных единицах:
копейках для `RUB` и Stars для `XTR`. Успешные ответы намеренно не содержат
внутренние ID БД, UUID доступа или subscription token.

### POST /vpn/payment-intents/

Создаёт короткоживущий intent после проверки feature flag, обеих цен и
доступной ёмкости VPN fleet.

```json
{"username": "1487189460", "currency": "RUB"}
```

`200 OK` для `RUB`:

```json
{
  "title": "VLESS VPN — 30 дней",
  "description": "Персональная VPN-подписка на 30 дней",
  "invoice_payload": "64-symbol-lowercase-hex-random-value",
  "currency": "RUB",
  "provider": "yukassa",
  "provider_data": {"receipt": {"items": []}},
  "send_email_to_provider": true,
  "need_email": true,
  "price": 19900,
  "expires_at": "2026-07-16T12:15:00+03:00"
}
```

`200 OK` для `XTR`:

```json
{
  "title": "VLESS VPN — 30 дней",
  "description": "Персональная VPN-подписка на 30 дней",
  "invoice_payload": "64-symbol-lowercase-hex-random-value",
  "currency": "XTR",
  "provider": "stars",
  "stars_price": 150,
  "expires_at": "2026-07-16T12:15:00+03:00"
}
```

Ошибки: `400 bad_payment_data`, `404 vpn_product_not_configured`,
`409 vpn_sales_disabled`, `503 vpn_capacity_unavailable`.

### POST /vpn/pre-checkout/

```json
{
  "username": "1487189460",
  "invoice_payload": "64-symbol-lowercase-hex-random-value",
  "currency": "RUB",
  "amount": 19900
}
```

Успех: `200 OK` с `{"status": "APPROVED"}`. Ошибки:
`400 bad_payment_data`, `404 payment_intent_not_found`,
`409 payment_intent_mismatch`, `409 payment_intent_expired`,
`503 vpn_capacity_unavailable`. Повтор точного уже одобренного pre-checkout
идемпотентен.

### POST /vpn/payments/

Принимает уже состоявшийся Telegram `successful_payment`.

```json
{
  "username": "1487189460",
  "invoice_payload": "64-symbol-lowercase-hex-random-value",
  "provider": "yukassa",
  "charge_id": "provider-charge-001",
  "currency": "RUB",
  "amount": 19900
}
```

Новая или ещё обрабатываемая receipt возвращает `202 Accepted` с
`{"status": "ACCEPTED"}`; уже применённая receipt — `200 OK` с
`{"status": "APPLIED"}`. После одобренного pre-checkout текущие feature flag,
состояние нод, активность/цена Product и истёкший TTL не блокируют сохранение
платежа. Ошибки: `400 bad_payment_data`, `404 payment_intent_not_found`,
`409 payment_intent_mismatch`, `409 payment_identity_conflict`.

### POST /vpn/status/

Запрос: `{"username": "1487189460"}`. Ответ всегда `200 OK` и содержит один из
статусов `NOT_PURCHASED`, `PREPARING`, `READY`, `EXPIRED`, `DISABLED`.
`expired_at` присутствует для существующего доступа. Поле `subscription_url`
присутствует только для `READY`. Административно архивный `is_active=False`
доступ считается `NOT_PURCHASED`, тогда как активные lifecycle-состояния
`EXPIRED` и `DISABLED_REFUND` остаются видимыми как `EXPIRED` и `DISABLED`:

```json
{
  "status": "READY",
  "expired_at": "2026-08-15T12:00:00+03:00",
  "subscription_url": "https://mtprotokeys.ru/api/v1/vpn/subscriptions/<token>/"
}
```

### POST /vpn/reissue/

Запрос: `{"username": "1487189460"}`. Успех — `202 Accepted` с
`{"status": "PREPARING"}`; стабильная subscription URL не меняется. Ошибки:
`404 vpn_access_not_found`, `409 vpn_access_expired`,
`409 vpn_reissue_in_progress`. Архивный `is_active=False` доступ возвращает
`404 vpn_access_not_found`.

### Единый error DTO

Ошибки VPN bot API имеют безопасную форму:

```json
{
  "code": "stable_machine_code",
  "message": "Безопасное сообщение пользователю",
  "detail": {}
}
```

Validation errors возвращают `400 bad_payment_data`, неверный bot token —
`403 forbidden`, неподдерживаемый HTTP-метод — `405 method_not_allowed`, а
непредвиденная внутренняя ошибка — безопасный `500 internal_error`. Malformed и
не-UTF-8 JSON, JSON scalar и неизвестные поля запроса считаются
`400 bad_payment_data`; лишние поля не игнорируются. Request values, invoice
payload, provider charge/payload, subscription token и UUID никогда не
отражаются в error body. Для mutating requests request logger сохраняет только
method/path, а headers и body целиком заменяет на `[redacted]` до записи в log.

### Маппинг Telegram-бота на VPN API

| Действие в боте | Backend contract |
|---|---|
| Открыть «VLESS VPN» | `POST /vpn/status/` |
| Купить за RUB или Stars | `POST /vpn/payment-intents/`, payload передаётся в Telegram без изменений |
| Telegram pre-checkout случайного VPN payload | `POST /vpn/pre-checkout/`; bot отвечает `ok=false` с безопасным `message` при отказе backend |
| Telegram successful payment случайного VPN payload | `POST /vpn/payments/`; после `ACCEPTED`/`APPLIED` бот немедленно сообщает о подготовке |
| Перевыпустить готовый доступ | `POST /vpn/reissue/`; bot сразу показывает `PREPARING` |

Статические payload `payment`, `payment_stars`,
`gift_certificate_yukassa` и `gift_certificate_stars` остаются закреплены за
существующими MTProto/gift flows. Все остальные invoice payload проверяет VPN
backend как случайный intent; текст invoice и валюта не выбирают продукт.

---

## GET /api/v1/vpn/subscriptions/&lt;token&gt;/

Публичный read-only endpoint использует стабильный URL-safe token с энтропией
не менее 256 бит. `200 text/plain` содержит Base64 списка VLESS+REALITY/TCP
ссылок для ordered active/available/READY нод с exact evidence
`published_revision`; IPv6 authority заключается в `[]`.

| Состояние | Ответ |
|---|---|
| неизвестный/архивный token | `404` |
| initial credential не опубликован | `503`, `Retry-After: 30` |
| истёкший или `DISABLED_REFUND` | `200` с пустым телом |
| shared Redis limit превышен | `429` с `Retry-After` |
| Redis throttle недоступен | `503` с `Retry-After: 30` |

Все ответы содержат `Cache-Control: private, no-store` и
`X-Content-Type-Options: nosniff`. GET не пишет в БД и не запускает provision.
Token не попадает в access logs/Redis key: throttle использует SHA-256 token и
trusted source IP. Plain HTTP только отвечает `308` на тот же HTTPS URL;
Django отдаёт subscription только за HTTPS proxy. Logging filter редактирует
request-derived path/query и уже материализованный `request.GET` до формирования
AdminEmail technical report.

Compatibility gate декодирует canonical outer Base64, запрещает trailing
newline/CR и строгим supported-client parser проверяет scheme, UUID, authority,
ordered query shape и фиксированный REALITY profile каждой строки.

## Исходящие запросы к VDS

Бэкенд общается с FastAPI-сервисами на VDS через HTTP. Выдача/перевыпуск ключа — это запись в БД + Celery-таск `push_key_to_servers_task`, который фан-аутит секрет на **все здоровые** VDS. Доставка идемпотентна и поддерживает ротацию: POST `/api/users`; если пользователь уже есть (`409`) — секрет ротируется через PATCH (новый перевыпущенный токен замещает старый; PATCH тем же секретом — безопасный no-op).

| Действие | Метод | URL | Тело |
|----------|-------|-----|------|
| Доставить ключ (POST, на `409` → PATCH-ротация) | POST/PATCH | `{server.internal_url}/api/users` | `{username, secret}` |
| Удалить | DELETE | `{server.internal_url}/api/users` | `{usernames: [...]}` |

Таймаут: `VDS_REQUEST_TIMEOUT` секунд. При исчерпании ретраев сервер помечается `is_healthy=False`; восстановление и бэкфилл ключей — через health-check + `sync_keys_to_vds_task`.
