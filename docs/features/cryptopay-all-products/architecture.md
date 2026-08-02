# Crypto Pay для всех текущих продуктов — архитектура

- **Статус:** approved
- **Scope revision:** 2
- **Трассируемые требования:** BR-001–BR-012, AC-001–AC-012
- **Основание:** `business.md` утверждён; пользователь отдельно утвердил
  направление с локальными intent, HMAC и secret-path webhook, exact-once
  fulfillment, post-commit Telegram-уведомлением, reconciliation раз в 10 минут,
  точный create/reuse response и безопасный admin alert для правильно
  подписанных неизвестных или несогласованных webhook.

## История revisions

| Revision | Статус | Изменение |
|---|---|---|
| 1 | superseded | Исходная архитектура для BR-001–BR-010 и AC-001–AC-010. |
| 2 | current | Добавлены точный create/reuse response и безопасный admin alert по BR-011–BR-012 / AC-011–AC-012; остальная архитектура revision 1 сохранена. |

## 1. Границы решения

Изменение остаётся внутри существующих `apps.payments`, `apps.vpn`,
`apps.notifications`/`apps.core`, конфигурации Django/Celery и Telegram-бота.
Новое Django-приложение, общий framework платёжных провайдеров, собственный
курс, отдельный прайс, кошелёк, refund flow и outbox-таблица не вводятся.

За основу берутся существующие компоненты:

- `Product`, `Payment`, `PaymentKindEnum`, `PaymentProviderEnum`;
- `CreatePaymentService` для MTProto;
- `FulfillVPNPurchaseService` для VPN;
- `CreateGiftCertificateService` для подарка;
- существующие selectors пользователей, товаров, ключей, VPN-подписок и
  сертификатов;
- `SendNotificationService`/Telegram transport и Celery;
- `BotAuthToken` и текущий `BackendClient` бота.

Stars callbacks, invoice payload и successful-payment обработка не меняют
семантику. Crypto Pay — отдельный backend-owned поток; бот не принимает webhook
и не подтверждает оплату.

### Рассмотренные варианты

1. **Выбран: локальный intent в `apps.payments` и тонкий Crypto Pay client.**
   Даёт snapshot цены, устойчивую корреляцию, повторное использование счёта,
   exact-once gate и диагностику без нового слоя.
2. Хранить только `invoice_id` в `Payment` и выдавать непосредственно из
   webhook. Не подходит: до оплаты нет `Payment`, негде обеспечить повторное
   использование и безопасно восстанавливать незавершённую выдачу.
3. Создать обобщённый provider/order framework или отдельное приложение.
   Отклонено: Stars не переводятся на новый flow, второго текущего потребителя
   абстракции нет, объём и риск выше утверждённого scope.

## 2. Компоненты и ответственность

### `CryptoPaymentIntent`

Одна новая модель в `apps.payments` хранит локальную покупку до и после оплаты.
Она наследует `BaseDjangoModel` и содержит:

| Поле | Назначение |
|---|---|
| `public_id` | Уникальный случайный UUID; единственное значение в provider `payload`, без PII. |
| `initiator` | FK на `SystemUser`; владелец результата независимо от плательщика общей ссылки. |
| `purchase_kind` | Существующий `PaymentKindEnum`: MTProto, VPN или gift. |
| `product_code` | Snapshot выбранного backend-ом товара: `mtproto_30d` или `vpn_30d`. |
| `rub_amount` | Точная Decimal-сумма RUB, полученная из сохранённой цены в копейках на момент создания. |
| `status` | Состояние lifecycle, описанное ниже. |
| `provider_invoice_id` | Nullable до успешного `createInvoice`, затем уникальный ID Crypto Pay. |
| `provider_invoice_url` | `bot_invoice_url`, показываемый пользователю. |
| `provider_created_at` | Время создания из provider response. |
| `provider_expires_at` | Время истечения из provider response; источник срока в ответе боту и проверке delayed webhook. |
| `paid_at` | Подтверждённое Crypto Pay время оплаты. |
| `fulfillment_attempted_at` | Время последней попытки применения. |
| `fulfilled_at` | Время успешной фиксации продукта. |
| `notification_sent_at` | Время успешной отправки результата инициатору. |
| `payment` | Nullable `OneToOneField` на итоговый `Payment`, `on_delete=PROTECT`. |
| `last_error_code` | Короткий диагностический код последней create/fulfillment/notification ошибки, без секретов и raw body. |

`created_at`/`updated_at` и `is_active` не дублируются. `is_active` не кодирует
provider lifecycle; для этого используется `status`.

Состояния:

- `CREATING` — локальная конкурентная резервация перед provider call;
- `ACTIVE` — счёт создан и может быть повторно возвращён;
- `LOCAL_EXPIRED` — локальный срок прошёл, счёт больше не переиспользуется, но
  delayed paid webhook всё ещё может его завершить;
- `PROCESSING` — одна попытка fulfillment получила compare-and-set claim;
- `RETRYABLE` — валидная оплата подтверждена, но fulfillment завершился
  временной ошибкой;
- `FULFILLED` — `Payment` и продукт атомарно зафиксированы;
- `CREATE_FAILED` — provider не создал пригодный счёт; следующий запрос может
  создать новый;
- `PROVIDER_EXPIRED` — `getInvoices` подтвердил неоплаченный terminal expiry.

Невалидный webhook не меняет intent в terminal-состояние: иначе посторонний или
повреждённый запрос мог бы заблокировать последующее корректное событие.

Ограничения БД:

- уникальный `public_id`;
- уникальный nullable `provider_invoice_id`;
- partial unique constraint на `(initiator, purchase_kind)` для статусов
  `CREATING` и `ACTIVE` — одновременно существует не более одного создаваемого
  или переиспользуемого счёта одного вида;
- отдельный partial unique constraint на `Payment(provider, charge_id, kind)`
  при `provider="crypto_pay"`, не затрагивающий возможные legacy-дубликаты
  MTProto других провайдеров.

### Enum и mapping

В `PaymentProviderEnum` добавляется `CRYPTO_PAY = "crypto_pay"`. Нового purchase
enum нет: используются существующие `PaymentKindEnum` и `ProductCodeEnum`.

Backend, а не бот, применяет фиксированное отображение:

| `purchase_kind` | `product_code` | Fulfillment |
|---|---|---|
| `subscription` | `mtproto_30d` | `CreatePaymentService` |
| `vpn_subscription` | `vpn_30d` | `FulfillVPNPurchaseService` |
| `gift_certificate` | `mtproto_30d` | `CreateGiftCertificateService` |

Gift намеренно использует текущую цену MTProto согласно BR-002. Произвольная
пара kind/code из bot request не принимается.

### `CryptoPayClient`

Тонкая `@final` frozen dataclass с инъецированными `base_url`, API token и HTTP
timeout. Она реализует только два требуемых метода:

- `create_invoice(...) -> CryptoInvoiceDTO`;
- `get_invoices(*, invoice_ids: list[int]) -> list[CryptoInvoiceDTO]`.

Клиент передаёт token только в `Crypto-Pay-API-Token`, использует HTTPS,
проверяет envelope `ok/result`, преобразует строки сумм в `Decimal` и provider
timestamps в timezone-aware datetime. HTTP/timeout, `ok=false` и malformed
response становятся доменными infra-исключениями из `apps.payments.exceptions`;
raw token и полный ответ не включаются в исключения и логи.

Официальный mainnet default — `https://pay.crypt.bot`; testnet задаётся тем же
настраиваемым `base_url` как `https://testnet-pay.crypt.bot`. Внешняя библиотека
Crypto Pay не нужна: существующий `requests` достаточен, а boundary мал и
полностью мокается через `responses`.

### Сервисы

`CreateOrReuseCryptoInvoiceService` зависит через поля dataclass от selectors,
`CryptoPayClient` и clock. Он отвечает только за выбор продукта, snapshot цены,
конкурентную резервацию и создание/повторное использование invoice. Его output
DTO содержит `invoice_url: str`, `rub_amount: Decimal`, `expires_at: datetime` и
`reused: bool`; один DTO используется новым и повторным путём.

`ApplyCryptoPaymentService` зависит от трёх существующих fulfillment-сервисов,
selectors итогового `Payment`/результата и post-commit enqueue функции. Он не
реализует выдачу продукта повторно. В зависимости от `purchase_kind` он передаёт
в существующий сервис:

- `username=intent.initiator.username`;
- `provider=PaymentProviderEnum.CRYPTO_PAY`;
- `charge_id=str(intent.provider_invoice_id)`;
- для VPN — сохранённый `product_code`.

После существующего сервиса итоговый `Payment` находится по provider identity и
kind, привязывается к intent, и intent переводится в `FULFILLED` в той же
транзакции. `CreatePaymentService` получает обратносуместимый keyword-флаг
success-нотификации с default `True`: Stars сохраняет текущий результат, а
Crypto-вызов передаёт `False`, чтобы все три Crypto kind использовали одну
durable post-commit доставку без двойного MTProto-сообщения.

Тонкая `notify_crypto_purchase_task(intent_id)` использует существующий
notification/Telegram transport, формирует результат по связанным доменным
данным и после успешной отправки заполняет `notification_sent_at`. Ограниченные
Celery retries покрывают временный Telegram error; reconciliation повторно
ставит уведомление для `FULFILLED` intent без `notification_sent_at`. Отдельная
outbox-модель не нужна: intent является durable ledger этой доставки.

Для правильно подписанного, но семантически отклонённого webhook view/service
передаёт отдельный безопасный DTO в инъецированную enqueue-функцию. Тонкая
Celery-задача форматирует operational warning и отправляет его администратору
через существующий `apps.core.telegram.transport.send_telegram_message` с
`settings.MY_TELEGRAM_ID`. Новый notification framework или persistent alert
model не создаются; `apps.notifications` продолжает обслуживать только уже
описанные пользовательские result templates.

## 3. Создание и повторное использование счёта

Защищённый контракт:

```text
POST /api/v1/payments/crypto/invoices/
Bot-Auth-Token: <existing backend token>

{
  "username": "1487189460",
  "purchase_kind": "subscription|vpn_subscription|gift_certificate"
}
```

Успешный ответ для нового и повторно используемого invoice одинаков (`200`):

```json
{
  "invoice_url": "https://t.me/CryptoBot?...",
  "rub_amount": "99.00",
  "expires_at": "2026-08-02T12:30:00Z",
  "reused": false
}
```

DRF serializer использует `DecimalField(decimal_places=2)`, поэтому точное
значение `Decimal` сериализуется decimal-safe JSON-строкой (`"99.00"`), а не
binary float. Новый provider invoice возвращает `reused=false`; существующий
активный intent возвращает сохранённые URL, `rub_amount` и expiry с
`reused=true`.

Алгоритм:

1. Найти существующего инициатора и backend mapping kind → product code.
2. Если есть `ACTIVE` intent с `provider_expires_at > now`, вернуть сохранённые
   URL, `rub_amount` и expiry с `reused=true` без обращения к Crypto Pay.
3. Просроченный `ACTIVE` перевести условным `UPDATE` в `LOCAL_EXPIRED`.
4. Найти активный `Product`, проверить `currency == "RUB"`, положительную цену
   и целое число сохранённых копеек. Рассчитать
   `rub_amount = Decimal(product.price) / Decimal("100")` с двумя знаками, без
   float и без запроса курса.
5. Создать `CREATING` intent с новым `public_id`. Partial unique index является
   арбитром гонки. Проигравший запрос перечитывает победителя: готовый `ACTIVE`
   возвращает тот же invoice; ещё `CREATING` отвечает retryable `409`.
6. Вызвать provider **вне** долгой DB-транзакции, чтобы не удерживать SQLite
   write lock во время сети.
7. Отправить ровно:

```json
{
  "currency_type": "fiat",
  "fiat": "RUB",
  "amount": "99.00",
  "accepted_assets": "USDT,TON",
  "expires_in": 1800,
  "payload": "<opaque public_id>"
}
```

   `description` может содержать только публичное название продукта. Telegram
   ID, username, email и иные PII не передаются.
8. Проверить provider response и условно обновить всё ещё `CREATING` intent до
   `ACTIVE`, сохранив invoice ID, `bot_invoice_url`, created/expiration dates.
   Вернуть сохранённые URL, `rub_amount`, expiry и `reused=false`.
   При provider/malformed-response ошибке перевести intent в `CREATE_FAILED` и
   вернуть retryable `502/503` с безопасным пользовательским сообщением.

`CREATING`, который старше заранее настроенного lease, равного удвоенному HTTP
timeout, следующая попытка условно переводит в `CREATE_FAILED`. Это позволяет
повторить запрос после падения процесса между provider response и локальным
update, не удерживая сетевой вызов внутри транзакции. Ссылка такого orphan
invoice пользователю не была возвращена.

## 4. Webhook и проверка оплаты

Публичный контракт не использует `BotAuthToken`:

```text
POST /api/v1/payments/crypto/webhooks/<CRYPTOPAY_WEBHOOK_SECRET>/
crypto-pay-api-signature: <hex HMAC-SHA256>
Content-Type: application/json
```

Порядок проверок до любого fulfillment:

1. Сравнить secret-path с backend-only setting через constant-time compare;
   неверный secret получает `404`.
2. Прочитать raw `request.body`. Ключ HMAC равен бинарному
   `SHA256(CRYPTOPAY_API_TOKEN)`, подпись — hex
   `HMAC-SHA256(key, raw_body)`; сравнение выполняется `compare_digest`.
   Отсутствующая/неверная подпись получает `401`.
3. Только после HMAC разобрать JSON в строгий webhook DTO.
4. Принять только `update_type="invoice_paid"` и `payload.status="paid"`.
5. Найти intent по `provider_invoice_id` и проверить:
   - `payload == str(intent.public_id)`;
   - `currency_type == "fiat"` и `fiat == "RUB"`;
   - `Decimal(amount) == intent.rub_amount`;
   - набор `accepted_assets` равен `{"USDT", "TON"}`;
   - `paid_asset` входит в `{"USDT", "TON"}`;
   - provider expiration соответствует сохранённой;
   - `paid_at` присутствует и не позже сохранённого `provider_expires_at`.
6. Передать тот же проверенный `CryptoInvoiceDTO` в
   `ApplyCryptoPaymentService`.

Текущий wall clock и локальный `LOCAL_EXPIRED` не являются причиной отказа:
решающим является своевременный provider `paid_at`. Поэтому корректный delayed
webhook завершает покупку после локального expiry.

HTTP semantics:

- уже `FULFILLED` intent с тем же согласованным invoice — `200`, no-op;
- успешное новое fulfillment — `200`;
- неверный secret/HMAC — `404/401`, без admin alert;
- malformed request до получения проверяемого event DTO — `400`, без выдачи;
- неподдерживаемый signed update после успешной HMAC-проверки — `400`, без
  выдачи;
- правильно подписанный unknown/mismatch — `200`, без выдачи, только после
  структурированного лога и успешной постановки безопасного admin warning;
  событие является семантически обработанным, а повторная доставка не может
  исправить неизвестную identity или несогласованные сохранённые реквизиты;
- если enqueue admin warning временно недоступен — `503`, чтобы provider retry
  повторил signed event и предупреждение не потерялось;
- временная DB/fulfillment ошибка — `503`, intent остаётся `RETRYABLE` или
  возвращается в него транзакционным rollback; provider может повторить.

После успешной HMAC-проверки неизвестный или несогласованный invoice логируется
структурированно и ставит admin warning. Допустимые поля обоих каналов:
стабильный `reason`, provider `update_id`, provider `invoice_id` и локальный
числовой `intent_id`, только когда он найден. Не включаются API token,
secret-path, signature, raw body, payload/public ID, Telegram ID или username,
invoice URL, gift code и VPN URL. Reason codes фиксированы по каждой проверке,
например `unknown_invoice`, `payload_mismatch`, `fiat_mismatch`,
`amount_mismatch`, `accepted_assets_mismatch`, `paid_asset_mismatch` и
`status_mismatch`.

## 5. Exact-once, транзакции и SQLite

`select_for_update()` сам по себе не считается механизмом корректности, потому
что SQLite не даёт требуемой row-lock семантики. Корректность обеспечивают БД
constraints и условные updates:

1. Apply выполняет `UPDATE ... SET status=PROCESSING WHERE id=? AND payment_id
   IS NULL AND status IN (ACTIVE, LOCAL_EXPIRED, RETRYABLE)`.
2. Только запрос с `updated_rows == 1` вызывает доменный fulfillment в том же
   `transaction.atomic()`.
3. Existing domain service создаёт продукт и `Payment`; Crypto partial unique
   constraint не допускает второй `Payment` для той же provider identity/kind.
4. Intent связывается с `Payment` и становится `FULFILLED` до commit.
5. Enqueue уведомления и уже существующие provisioning/push effects выполняются
   через `transaction.on_commit`.

Если transaction откатывается, claim `PROCESSING`, продукт, `Payment` и связь
intent откатываются вместе. Сервис фиксирует безопасный `RETRYABLE` отдельным
коротким update после rollback и пробрасывает временную ошибку. При конкурентном
webhook/reconciliation один процесс получает claim; второй отвечает `503`, если
первый ещё работает, либо `200` после чтения `FULFILLED`. SQLite `database is
locked` классифицируется как временная ошибка, а не как отказ оплаты.

Доменная идемпотентность остаётся второй защитой: VPN и gift уже идемпотентны по
provider identity; для MTProto Crypto identity защищается новым частичным
constraint. Stars и legacy non-XTR строки/контракты не меняются.

## 6. Reconciliation

Celery Beat каждые 10 минут вызывает одну задачу
`reconcile_crypto_payments_task`.

1. Selector выбирает intent без `payment` в состояниях `ACTIVE`,
   `LOCAL_EXPIRED` и `RETRYABLE`; `PROCESSING` существует только внутри
   незавершённой atomic-транзакции, а `CREATING`, `CREATE_FAILED`,
   `PROVIDER_EXPIRED` и `FULFILLED` не запрашиваются как незавершённые оплаты.
2. Invoice IDs передаются в `getInvoices(invoice_ids=...)` ограниченными
   provider batches.
3. `paid` invoice проходит те же проверки DTO и тот же
   `ApplyCryptoPaymentService`, что webhook.
4. Provider `expired` условно переводит локальный `ACTIVE/LOCAL_EXPIRED` в
   `PROVIDER_EXPIRED`; provider `active` не меняет результат.
5. Ошибка одного invoice логируется и не останавливает остальные; временная
   общая provider ошибка завершает задачу ошибкой для стандартного Celery retry.
6. В том же запуске `FULFILLED` intent без `notification_sent_at` повторно
   ставятся на post-commit notification delivery.

Задача не запрашивает курсы, не создаёт новые счета и не меняет product price.

## 7. Bot flow

На каждом из трёх экранов клавиатура сохраняет Stars первой строкой и добавляет
Crypto Pay второй:

- `pay_crypto` для MTProto;
- `vpn_pay_crypto` для VPN;
- `gift_crypto` для подарка.

Три handler вызывают один метод `PaymentsClient.create_crypto_invoice(...)` с
соответствующим `purchase_kind`. Клиент передаёт существующий
`Bot-Auth-Token` и отображает ответ в dataclass с `invoice_url`, строковым точным
`rub_amount`, `expires_at` и `reused`; float conversion не выполняется. Crypto
token и webhook secret в bot settings отсутствуют.

При `200` бот показывает срок и URL-кнопку CryptoBot. При `409`, provider
`502/503` или backend error текущий общий error handling показывает безопасный
текст о невозможности создать счёт и позволяет повторно нажать Crypto Pay.
Никакой polling оплаты и successful-payment route для Crypto в боте не
добавляется: результат после webhook/reconciliation отправляет backend.

## 8. Конфигурация и безопасность

Backend settings:

- `CRYPTOPAY_API_TOKEN` — обязателен при включённом flow;
- `CRYPTOPAY_BASE_URL` — mainnet default с возможностью официального testnet;
- `CRYPTOPAY_WEBHOOK_SECRET` — отдельный случайный secret-path;
- `CRYPTOPAY_REQUEST_TIMEOUT` — короткий HTTP timeout;
- константы кода: accepted assets `USDT,TON`, invoice expiry `1800`, reconcile
  schedule `*/10` минут.

Token и webhook secret передаются только backend Django/Celery через deployment
environment. Bot и provider payload их не получают. Secret-path редактируется в
Crypto Pay app settings как HTTPS webhook URL. Request logging должен
редактировать этот path до записи, аналогично существующей redaction VPN token.

Admin регистрирует `CryptoPaymentIntent` как диагностический read-only список:
фильтры по status/kind, поиск по локальному public ID/provider invoice ID,
отображение initiator, RUB snapshot, paid/fulfilled/notified timestamps и
связанного `Payment`. Add/delete и любые actions отсутствуют; POST-изменение
полей запрещено. Действия «mark paid» нет.

## 9. Миграция, rollout и rollback

Миграция аддитивна:

1. создаёт новую таблицу intent и её индексы/constraints;
2. добавляет Crypto Pay choice и только Crypto-specific partial uniqueness к
   `Payment`;
3. не переписывает `Product`, существующие `Payment`, ключи, VPN-подписки или
   сертификаты;
4. отдельная data migration добавляет только недостающие notification templates
   результата VPN/gift, не изменяя Stars templates.

Порядок rollout: применить миграцию и backend/config, запустить worker/beat,
настроить provider webhook, затем развернуть bot-кнопки. До появления кнопок
новый flow недоступен пользователю; Stars продолжает работать.

При code rollback таблица и новые nullable/choice-compatible данные остаются в
БД (expand-only rollback); старый код их игнорирует, Stars остаётся работоспособен.
Production reverse migration после реальных оплат не выполняется, чтобы не
потерять audit/intents. Webhook отключается у provider, bot откатывается до
Stars-only. Уже зафиксированные `Payment` и выданные продукты не откатываются и
не возвращаются автоматически, что соответствует non-goals.

## 10. Ошибки и наблюдаемость

Доменные ошибки размещаются в `apps.payments.exceptions` и разделяются на:

- user/input: неизвестный user/kind, неактивный продукт, неверная RUB цена;
- provider infra: timeout/network, `ok=false`, malformed response;
- webhook auth/contract mismatch;
- retryable fulfillment/SQLite contention.

Логи содержат стабильные reason codes. Правильно подписанный unknown/mismatch
дополнительно вызывает инъецированный enqueue безопасного admin warning через
существующий core Telegram transport; invalid secret/HMAC не вызывает его.
Reconciliation пишет итоговые counters: checked, paid, fulfilled,
provider_expired, retryable_failed и notifications enqueued. Django Admin
показывает сохранённый lifecycle, но не заменяет логи и warning для unknown
webhook. Новая metrics/monitoring инфраструктура в scope не добавляется.

## 11. Ожидаемая поверхность реализации

Конкретные имена файлов могут быть объединены по существующему размеру модулей,
но компоненты не должны выйти за этот список:

- `src/apps/payments/`: model/admin, enums, selectors, exceptions, новая
  migration, Crypto DTO/client/create/apply services, API serializers/views/URL,
  reconciliation, user-result notification и safe admin-warning tasks, явные
  `__init__.py` exports;
- существующие `apps.notifications` templates и
  `apps.core.telegram.transport` используются как границы отправки; отдельные
  monitoring модели/слои не добавляются;
- минимальная обратносуместимая правка `CreatePaymentService`, позволяющая
  Crypto orchestration отключить его собственную success notification;
- `src/config/settings/payments.py`, `src/config/settings/celery.py`, request-path
  redaction и backend env/deploy examples;
- `bot/src/domains/payments/client.py`, payments/VPN handlers, keyboards,
  messages и их exports/wiring;
- тесты соответствующих слоёв;
- после реализации — профильные `docs/CONTRACTS.md`, `docs/MODELS.md`,
  `docs/ARCHITECTURE.md`, `docs/BUSINESS.md` и `docs/apps/PAYMENTS.md`.

Не ожидаются изменения моделей `users`, `vds`, `vpn`, Stars contracts или
состава/длительности продуктов.

## 12. Проверки

### Модель и миграция

- additive forward migration и сохранение legacy rows;
- partial uniqueness для active intent и Crypto `Payment`, без изменения legacy
  subscription duplicates;
- read-only admin и отсутствие mark-paid action.

### Client и create service

- точная конверсия 9900/14900 копеек в `99.00`/`149.00` RUB через Decimal;
- gift → `mtproto_30d`, VPN → `vpn_30d`;
- точные `currency_type`, `fiat`, `accepted_assets`, `expires_in` и opaque payload;
- output DTO/DRF response нового invoice содержит сохранённый decimal-safe
  `rub_amount` и `reused=false`; reuse активного invoice возвращает те же
  URL/expiry/amount и `reused=true`;
- provider error остаётся повторяемым;
- TransactionTestCase гонки оставляет один `CREATING/ACTIVE` intent на пару.

### Webhook и apply

- известный HMAC test vector проверяется по raw bytes, а не re-serialized JSON;
- secret-path, event/status, invoice ID, payload, fiat/amount, accepted/paid asset
  и paid_at validation;
- каждый правильно подписанный unknown/mismatch reason создаёт один
  enqueue-вызов с разрешёнными provider/local IDs и стабильным reason, после
  чего webhook отвечает `200` без fulfillment;
- payload admin warning явно не содержит token, secret, signature, raw body,
  PII, invoice URL, gift code или VPN URL; invalid secret/HMAC alert не вызывает;
- MTProto issue/extend, VPN issue/extend, gift creation через существующие
  services;
- инициатор получает результат, плательщик webhook не используется как owner;
- duplicate — `200` без второго продукта/Payment;
- своевременно оплаченный delayed webhook после local expiry выполняется;
- временная ошибка оставляет retryable intent и возвращает non-2xx;
- callback уведомления не исполняется до commit, Telegram retry и
  `notification_sent_at`.

### Reconciliation, API и bot

- paid unfinished восстанавливается тем же apply service; fulfilled no-op;
- schedule ровно 10 минут и batch/error isolation;
- create endpoint требует `Bot-Auth-Token`, webhook его не требует, но требует
  обе approved защиты;
- три bot-клавиатуры имеют Stars первой и Crypto второй строкой;
- bot client decimal-safe отображает все четыре поля create response; три
  callback передают правильный kind и показывают URL/expiry;
- Stars handler, invoice payload и legacy successful-payment regression tests;
- полный `make test` и bot test suite.

## 13. Трассировка BR/AC

| Требование | Архитектурные разделы |
|---|---|
| BR-001 / AC-001 / AC-009 | 1, 7, 9, 12 |
| BR-002 / AC-003 | 2, 3, 12 |
| BR-003 / AC-003 | 3, 4, 12 |
| BR-004 / AC-002 / AC-004 | 2, 3, 5, 7 |
| BR-005 | 2, 4, 7 |
| BR-006 / AC-005 / AC-006 | 4, 5, 12 |
| BR-007 / AC-002 / AC-003 / AC-007 | 2–4, 8, 10 |
| BR-008 / AC-005 | 2, 5–7 |
| BR-009 / AC-008 | 5, 6, 12 |
| BR-010 | 3–6, 10, 12 |
| AC-010 | 8, 9, 12 |
| BR-011 / AC-011 | 2, 3, 7, 12 |
| BR-012 / AC-012 | 2, 4, 10–12 |

## 14. Явно вне решения

Не проектируются и не реализуются: изменение Stars, активы кроме USDT/TON,
crypto price/rates, recurring payments, refunds, wallet, новые duration/content,
ручной mark-paid, общий provider framework, отдельная event/audit/outbox таблица,
merge и production deploy.
