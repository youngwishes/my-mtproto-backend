# Контракты API

Все пути ниже абсолютные и включают базовый префикс `/api/v1`.

Если явно не указано иное, эндпоинты защищены заголовком `Bot-Auth-Token`.

---

## Users

### POST /api/v1/users/consent/status/

Read-only проверяет единое юридическое согласие. Отсутствующий пользователь
возвращает `false` и не создаётся.

```json
{"username": "1487189460"}
```

```json
{"legal_terms_accepted": false}
```

---

### POST /api/v1/users/consent/accept/

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

### POST /api/v1/users/first-free-link/

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

### POST /api/v1/users/check-first-free-link/

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

### POST /api/v1/users/referral/cabinet/

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

### POST /api/v1/users/referral/link/

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

### POST /api/v1/users/update-link/

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

### POST /api/v1/users/my-servers/

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
      "proxy_link": "tg://proxy?server=space.mtprotokeys.com&port=443&secret=ee..."
    }
  ]
}
```

**Ошибки:** `KeyDoesNotExist` (нет активного ключа и бесплатный период уже израсходован).

---

## Payments

`GET /api/v1/payments/products/vpn_30d/` возвращает активный VPN-товар в том же
формате, что и legacy `GET /api/v1/payments/`; legacy route остаётся MTProto alias.
Оба защищённых `Bot-Auth-Token` маршрута на каждом запросе добавляют один и тот
же глобальный список активных способов оплаты `payment_methods`, его
упорядоченную подпоследовательность активных приоритетных способов
`priority_payment_methods` и точную decimal-строку `rub_amount`.

Все три apple endpoint ниже принимают только перечисленные поля, защищены
`Bot-Auth-Token` и при отсутствующем или неверном токене возвращают `403`.
Клиент не может передать цену, ставку, баланс, дни, срок или ID ключа.

### POST /api/v1/payments/apples/status/

Возвращает вычисленный backend loyalty-статус и готовность к обмену.

**Запрос:**

```json
{
  "username": "1487189460"
}
```

**Ответ:** `200 OK`

```json
{
  "balance": 37,
  "eligible_purchase_count": 4,
  "level": "Садовник",
  "rate_percent": 10,
  "next_level_purchase_count": 7,
  "purchases_to_next_level": 3,
  "is_max_level": false,
  "redeemable_days": 2,
  "missing_apples": 0,
  "has_existing_key": true
}
```

Для `Мастер сада` оба next-level поля равны `null`, а `is_max_level=true`.
`redeemable_days` — число полных пакетов по 15; `missing_apples` — сколько не
хватает до первого пакета, либо `0`. Ни token, key ID, proxy link, ни URL не
возвращаются.

### POST /api/v1/payments/apples/redemptions/preview/

Создаёт неизменяемый, не списывающий яблоки предпросмотр. `mode` принимает
только `one_day` или `all`.

**Запрос:**

```json
{
  "username": "1487189460",
  "mode": "all"
}
```

**Ответ:** `200 OK`

```json
{
  "confirmation_id": 42,
  "mode": "all",
  "apples_spent": 30,
  "days": 2,
  "projected_expired_date": "21.08.26"
}
```

`one_day` всегда фиксирует 15 яблок и один день; `all` фиксирует наибольший
кратный 15 spend из текущего баланса и сохраняет остаток. Backend выбирает
собственный существующий active или expired MTProxy-ключ и рассчитывает дату
от `max(expired_date, preview_at)`. Preview не резервирует баланс и не меняет
ключ.

### POST /api/v1/payments/apples/redemptions/confirm/

Подтверждает только сохранённый owner-scoped предпросмотр; bot не повторяет
поля quote.

**Запрос:**

```json
{
  "username": "1487189460",
  "confirmation_id": 42
}
```

**Ответ:** `200 OK`

```json
{
  "apples_spent": 30,
  "days": 2,
  "expired_date": "21.08.26",
  "balance": 7
}
```

Confirm сохраняет quoted `apples_spent` и `days`: новый credit после preview
может увеличить баланс, но не размер обмена. Изменение expiry того же выбранного
ключа также допустимо; committed дата заново вычисляется как
`max(current_same_key_expiry, confirmation_at)+days` и поэтому может отличаться
от `projected_expired_date` в preview. Операция атомарно списывает ровно quoted
яблоки и продлевает этот же ключ. Повтор подтверждённого ID возвращает
идентичный сохранённый `200` без нового списания или продления.

Quote становится stale только если текущий selector выбирает другой ключ,
выбранный ключ удалён/недоступен или balance стал ниже quoted spend; такой
`400` не меняет баланс или срок и требует нового preview. Чужой, неизвестный
или некорректный confirmation ID является invalid confirmation и также даёт
`400` без mutation, но не классифицируется как stale.

Ошибки exact-input validation, отсутствующий пользователь, invalid mode/ID,
баланс меньше 15 (`InsufficientApples`, `detail.missing_apples`), отсутствие
ключа (`AppleKeyRequired`) и stale quote (`StaleAppleRedemption`) используют
стандартный user-safe `400` формат `{"error": "…", "detail": {…}}`.
Временная DB/storage ошибка на любом из трёх маршрутов возвращает `503`:

```json
{
  "error": "Не удалось завершить обмен яблок. Попробуйте ещё раз.",
  "detail": {}
}
```

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

### POST /api/v1/payments/platega/invoices/

Защищён `Bot-Auth-Token`. Принимает только `username` (Telegram ID) и
`purchase_kind` (`subscription`, `vpn_subscription` или `gift_certificate`):
бот не передаёт сумму, metadata, redirects или provider credentials. Создаёт
15-минутную Platega SBP-ссылку либо возвращает ещё живую ссылку того же
инициатора и purchase kind.

Успешный ответ — `200 OK` с ровно четырьмя полями:

```json
{
  "payment_url": "https://pay.platega.io/…",
  "rub_amount": "99.00",
  "expires_at": "2026-08-31T12:00:00Z",
  "reused": false
}
```

`rub_amount` — decimal-строка с двумя знаками из backend snapshot полной
пользовательской RUB-цены; она не уменьшается на provider commission и остаётся
`99.00` в intent, API и bot. Ошибки формы и неподдерживаемый kind используют DRF
`400`; текущий `creating`, `processing` или `retryable` intent возвращает `409`;
provider и временные storage failures возвращают `503` только с безопасным
reason code. Если обязательная строка `PaymentMethod(platega_sbp)` отсутствует,
backend не подставляет ставку по умолчанию и возвращает безопасный `503` с
`payment_method_unavailable` до provider POST.

### Platega outbound provider contract

Django backend creates an SBP transaction only with
`POST {PLATEGA_BASE_URL}/transaction/process`; there is no Platega GET method.
Request headers are `X-MerchantId`, `X-Secret` and `Content-Type: application/json`.
The JSON sends `paymentMethod: 2`, `paymentDetails` with a two-decimal numeric
RUB provider amount serialized directly from `Decimal`, the product description,
both `return` and `failedUrl` equal to backend `BOT_LINK`, a UUID-only `payload`,
and `metadata.userId` / `metadata.userName`. The provider amount is calculated
for each new intent from the current global payment-method setting as
`user_amount / (1 + commission_percent / 100)` and rounded once to two decimals
with `ROUND_HALF_UP`. Thus user amount `99.00` and commission `8.00%` send
numeric `paymentDetails.amount: 91.67`; `0.00%` sends `99.00`. The latter
metadata field falls back to string Telegram ID if a saved username is absent.

A usable creation response is exactly HTTP `200` with a JSON object containing
UUID `transactionId`, `status: "PENDING"`, and HTTPS `redirect`. All
provider-controlled response echoes, including `expiresIn`, `paymentMethod`,
`paymentDetails`, `return`, and `merchantId`, are ignored; backend assigns a
fixed local expiry of 15 minutes. Client errors expose only `timeout`,
`unavailable`, `malformed`, or `create_mismatch`; credentials, metadata, bodies
and payment URLs are not logged.

### POST /api/v1/payments/platega/callback/

Публичный callback не использует `Bot-Auth-Token`, DRF authentication или
permissions. До чтения JSON backend извлекает raw headers `X-MerchantId` и
`X-Secret`, вычисляет обе отдельные `secrets.compare_digest` проверки и только
затем объединяет результаты. Пустые configured credentials fail-closed.
Missing/invalid header возвращает пустой `401` без body parsing.

После успешной аутентификации принимается JSON-объект с пятью обязательными
ключами и необязательным provider echo `payload`:

```json
{
  "id": "6765c89d-4800-4e07-b45d-d886e696e87c",
  "amount": 99.0036,
  "currency": "RUB",
  "status": "CONFIRMED",
  "paymentMethod": 2,
  "payload": "492a37cf-49cf-43ac-a693-dbc942ac98e2"
}
```

`payload` не участвует в выборе intent или валидации и не передаётся в доменный
DTO; callback без него остаётся валидным. Другие дополнительные ключи
отклоняются до domain processing.

`amount` должен быть конечным JSON-числом. Integer, fraction и finite exponent
принимаются без продуктового ограничения на число целых или дробных знаков и
разбираются точно в Decimal без промежуточного binary float. Numeric string,
boolean, `null`, container, `NaN` и бесконечность недопустимы. Amount проходит
проверку, когда `received >= intent.rub_amount`; сравнение не округляет вход.
Поэтому `99`, `99.0036` и любая переплата валидны при сохранённых `99.00`, а
`98.999999999999999999` остаётся mismatch. Проверки transaction ID, точных
`RUB`, method `2`, статуса и состояния intent сохраняются.

Authenticated malformed JSON, missing/unrecognized extra/malformed fields, unknown
transaction, mismatch, unsupported status, normal/repeated `CANCELED` и
duplicate fulfillment возвращают пустой `200` без небезопасной выдачи.
`CHARGEBACKED` относится только к unsupported safe acknowledgement и не
запускает refund/revocation. Точный `CONFIRMED`, после успешной атомарной выдачи
и резервирования notification enqueue, также возвращает пустой `200`.
Временная DB/fulfilment/Celery publish ошибка или уже идущий concurrent
processing возвращает пустой `503`, чтобы тот же callback можно было повторить.

Для authenticated unknown/mismatch/unsupported backend делает один warning с
ровно тремя полями: `reason_code`, nullable internal `intent_id` и nullable
`provider_transaction_id`. По умолчанию callback body/headers,
settings/credentials, Telegram ID/username, metadata, payload, provider content
и payment URL не логируются. При временном
`PLATEGA_CALLBACK_DEBUG_LOGGING=true` успешно аутентифицированный запрос до
парсинга создаёт INFO-событие `platega_callback_request`: raw body,
method/path, Content-Type/User-Agent и только названия заголовков. Значения
`X-MerchantId`, `X-Secret`, Authorization и Cookie не попадают в событие;
неавторизованный запрос также не логируется. Флаг не меняет callback response
или доменную обработку. Endpoint не вызывает provider GET и не имеет polling
schedule.

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

### GET /api/v1/vpn/menu/?username=<telegram_id>

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

### POST /api/v1/vpn/reissue/

POST-only endpoint защищён permission `BotAuthToken` через заголовок
`Bot-Auth-Token`. Принимает только username Telegram-пользователя:

```json
{
  "username": "1487189460"
}
```

Для active VPN-подписки перевыпускает subscription token, VLESS UUID и Hysteria
secret, сохраняя `expired_at` и active-state. Успешный ответ — `200 OK` и ровно
два поля:

```json
{
  "expired_at": "2026-08-31T12:00:00+00:00",
  "subscription_url": "https://example.com/api/v1/vpn/subscriptions/new-token/"
}
```

Для отсутствующей, истёкшей или неактивной подписки возвращает `400`:

```json
{
  "error": "🔒 Перевыпуск VPN-ссылки доступен только после продления подписки.",
  "detail": {}
}
```

Повторный перевыпуск в пределах пяти минут возвращает `400` с тем же форматом:

```json
{
  "error": "🔒 Пожалуйста, подождите 5 минут с последнего обновления.",
  "detail": {}
}
```

Старая subscription URL сразу после успешного DB update возвращает `404`; новая
возвращает профили с новыми credentials. Один существующий post-commit scheduler
асинхронно ставит profile PUT delivery на активные VPN-ноды. Ответ не ждёт
завершения нод и не вводит readiness state.

### GET /api/v1/vpn/subscriptions/<token>/

Публичный endpoint. Успешный ответ имеет `200 OK`, `Content-Type: text/plain` и
`profile-title: mtprotokeys.com`; новый заголовок не изменяет существующие
subscription URL или Base64 payload.

### POST /api/v1/vpn/payments/buy/

Защищён `Bot-Auth-Token`. Фиксирует только VPN-платёж и принимает:

```json
{
  "username": "1487189460",
  "charge_id": "vpn_charge_001",
  "provider": "stars",
  "product_code": "vpn_30d"
}
```

Покупка или продление возвращает срок и текущую внешнюю subscription-ссылку.
Этот flow сохраняет её без явного перевыпуска; подтверждённый перевыпуск заменяет
её новым token:

```json
{
  "expired_at": "2026-08-31T12:00:00+00:00",
  "subscription_url": "https://example.com/api/v1/vpn/subscriptions/token/"
}
```

---

### GET /api/v1/payments/

Защищён `Bot-Auth-Token`. Возвращает данные MTProto-товара для формирования
Telegram-инвойса. `GET /api/v1/payments/products/<code>/` возвращает тот же контракт
для выбранного активного товара, включая `vpn_30d`.

**Ответ:** `200 OK`

```json
{
  "title": "MTPRoto Proxy — 30 дней",
  "description": "Прокси-ссылка на 30 дней для Telegram",
  "currency": "RUB",
  "provider_data": "{\"receipt\": ...}",
  "send_email_to_provider": true,
  "need_email": true,
  "price": 9900.0,
  "rub_amount": "99.00",
  "stars_price": 99,
  "payment_methods": ["platega_sbp", "stars", "crypto_pay"],
  "priority_payment_methods": ["platega_sbp", "crypto_pay"]
}
```

`price` хранится и возвращается в копейках: `9900.0` соответствует 99 RUB.
`rub_amount` аддитивно возвращает ту же цену как строку с ровно двумя
десятичными знаками, без float; `stars_price` хранит отдельную цену в Telegram
Stars. Все прежние product-поля сохраняют свой JSON-контракт.

`payment_methods` всегда присутствует и содержит только активные способы,
поддержанные кодом. Порядок фиксирован: активный `platega_sbp` всегда первый,
затем `stars`, затем `crypto_pay`; допустима любая активная подпоследовательность
или `[]`. Список глобален и одинаков для MTProto, VPN и подарочного сертификата.
Изменение в Django admin видно на следующем GET без перезапуска или кеша. Пустой
список является штатным состоянием, а отсутствие активного товара сохраняет
прежнюю ошибку `400`.

`priority_payment_methods` также всегда присутствует. Он содержит только
активные, поддержанные кодом и отмеченные как приоритетные способы в том же
фиксированном порядке и всегда является подпоследовательностью
`payment_methods`. Допустимы несколько значений, одно значение или `[]`;
настройка приоритета не меняет состав и порядок прежнего `payment_methods`.

---

### POST /api/v1/payments/buy/

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
| `provider` | string | `"yukassa"`, `"stars"`, `"crypto_pay"` или `"platega"` |

`provider` принимает значения общего `PaymentProviderEnum`: `yukassa`, `stars`,
`crypto_pay` или `platega`; штатные sync-вызовы бота используют первые два, а
Crypto/Platega fulfilment вызывает ту же доменную границу из сохранённого
intent. `charge_id` не может быть пустым; дополнительные клиентские поля,
включая цену и ставку, отклоняются.

**Ответ новой покупки или post-launch duplicate:** `200 OK`

```json
{
  "expired_date": "18.09.26",
  "loyalty": {
    "apples_earned": 5,
    "rate_percent": 5,
    "balance": 20,
    "eligible_purchase_count": 4,
    "level": "Садовник",
    "level_up": true,
    "next_purchase_rate_percent": 10
  }
}
```

Ставка берётся по count до оплаты; `loyalty` и `expired_date` сохраняются как
результат identity, поэтому повтор не продлевает ключ и не начисляет яблоки
повторно. Sync success-message отправляет только bot handler.

Identity подходящей оплаты, которая уже существовала при launch backfill,
возвращает единственный успешный tag:

```json
{
  "kind": "historical_replay"
}
```

Это ровно одно поле: `expired_date` и `loyalty` отсутствуют. Replay не создаёт
ключ, Payment или новую purchase-строку, не меняет count/balance и не вызывает
sync success-message.

### POST /api/v1/payments/gift-certificates/buy/

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
| `provider` | string | `"yukassa"`, `"stars"`, `"crypto_pay"` или `"platega"` |

**Ответ:** `200 OK`

```json
{
  "code": "KEY-ABCD-1234",
  "loyalty": {
    "apples_earned": 5,
    "rate_percent": 5,
    "balance": 5,
    "eligible_purchase_count": 1,
    "level": "Новичок",
    "level_up": false,
    "next_purchase_rate_percent": 5
  }
}
```

Непустой `charge_id` и exact-input правила те же, что у subscription buy.
Начисление, count и purchase принадлежат покупателю, не получателю сертификата;
активация к loyalty не относится. Post-launch duplicate возвращает неизменные
сохранённые `code` и `loyalty` без второго сертификата или начисления.

Для pre-launch identity ответ — тот же единственный
`{"kind":"historical_replay"}` без `code` и `loyalty`, product/payment/loyalty
mutation и success-message. Для Crypto/Platega normal result доставляет одна
post-commit provider notification task; она добавляет сохранённый loyalty-блок
к прежнему expiry/code шаблону, а historical replay не ставится и не
отправляется. Reconciliation не повторяет продуктовые или loyalty-эффекты.

### POST /api/v1/payments/gift-certificates/activate/

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
