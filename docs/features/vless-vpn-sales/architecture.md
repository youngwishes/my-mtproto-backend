# Архитектура продажи VLESS VPN-подписок

## Статус

`approved`

Технический дизайн явно подтверждён пользователем. Документ уточняет
утверждённый [продуктовый дизайн](business.md) относительно текущей архитектуры
центрального backend и является основанием для подготовки implementation plans.

## Решение

MVP состоит из двух независимо версионируемых, но контрактно связанных систем:

1. `my-mtproto-backend` — каталог, Telegram UX, приём факта платежа, срок
   подписки, публичная subscription URL и оркестрация желаемого состояния;
2. новый репозиторий `my-vless-vds-instance` — HTTPS API-агент на каждой
   VPN-ноде, локальный durable snapshot и прямое управление закреплённой версией
   Xray.

В центральном backend создаётся отдельное Django-приложение `apps/vpn`.
`apps/vds` и MTProto-agent не переиспользуются: у VPN другой runtime, формат
credential, готовность, reconcile и публичные параметры. `apps/music` не
затрагивается.

Центральная SQLite БД остаётся единственным источником истины. Один
`VPNAccess` принадлежит одному `SystemUser`, имеет одну стабильную subscription
URL и один желаемый UUID, общий для всех VPN-нод. Xray и локальные snapshots
агентов являются производным состоянием.

Внешняя панель, включая 3x-ui, не является источником истины и не участвует в
fulfillment. Оператор может установить 3x-ui только как необязательный
диагностический интерфейс без права изменять управляемый inbound. Агент управляет
Xray напрямую через закреплённый и протестированный Xray API/runtime.

## Компоненты и границы зависимостей

### `apps/payments`

`apps/payments` владеет каталогом, необработанным фактом успешного платежа и
единственной транзакцией применения платежа. В нём находятся:

- `Product` со стабильным nullable-кодом на expand-этапе;
- короткоживущий durable `PaymentIntent` с неизменяемыми параметрами invoice;
- существующий `Payment` как применённый факт оплаты;
- новый durable `PaymentReceipt` как входящий, ещё не обязательно применённый
  факт успешного платежа;
- `ApplyPaymentReceiptService`, который создаёт `Payment`, вызывает внедрённый
  fulfillment-контракт и завершает receipt в одной DB-транзакции.

`apps/payments` определяет контракт `VPNPaymentFulfillment` через `Protocol` или
callable DTO, но не импортирует `apps.vpn`. Реализация и module-level factory
находятся в `apps/vpn`: этот factory импортирует payment orchestrator и
инъектирует `FulfillVPNPurchaseService`. Поэтому разрешено направление
`vpn -> payments`, а обратного импорта нет. Ни payment view, ни bot handler не
создают и не изменяют `VPNAccess` напрямую.

### `apps/vpn`

`apps/vpn` владеет:

- доступами, нодами и связью применённого платежа с VPN-доступом;
- VPN fulfillment, reissue, refund deactivation и status services;
- генерацией subscription-ответа;
- HTTPS transport к агенту;
- задачами доставки, readiness, health-check и reconcile;
- составным factory для обработки `PaymentReceipt`.

Все ORM-запросы размещаются в `selectors.py`. Бизнес-операции выполняются
`@final` frozen dataclass services с `kw_only=True`, `slots=True`, `frozen=True`
и keyword-only `__call__`. Зависимые сервисы и transport передаются полями;
wiring выполняют только module-level factory functions. Celery tasks остаются
тонкими.

### Telegram-бот

Бот показывает отдельный раздел VPN, получает invoice только по коду
`vless_30d`, повторно проверяет продажу при pre-checkout и маршрутизует
`successful_payment` по точному invoice payload. Текст кнопки, валюта или
локализованное название не определяют fulfillment.

После сохранения `PaymentReceipt` бот сразу сообщает «Оплата принята, доступ
готовится». Subscription URL приходит отдельным Telegram-уведомлением только
после перехода соответствующей credential revision в `READY`.

### `my-vless-vds-instance`

Новый репозиторий повторяет эксплуатационные соглашения sibling-проекта
`my-mtproto-vds-instance`: отдельные тесты, Docker image/Compose, Ansible
inventory и воспроизводимый deploy по полному commit SHA. Он не является
поддиректорией центрального Django-приложения.

На каждой ноде агент управляет ровно одним выделенным VLESS + REALITY over TCP
inbound. Версия Xray и digest образа закрепляются в репозитории агента; upgrade
Xray является отдельным проверяемым изменением.

## Потоки данных

### Проверка продажи и выставление invoice

Продажа доступна, только если одновременно:

- `VPN_SALES_ENABLED=True`;
- существует один активный `Product(code="vless_30d")` с валидными
  рублёвой и Stars-ценой;
- существует хотя бы одна активная нода в состоянии `READY`, разрешённая для
  новых доступов, совместимая с agent contract и не превышающая лимит snapshot
  после добавления ещё одного доступа.

При запросе invoice backend повторяет эту проверку и создаёт короткоживущий
`PaymentIntent` с криптографически случайным непредсказуемым `invoice_payload`,
user, product, currency, amount и временем истечения. Бот передаёт payload в
Telegram без преобразования.

Pre-checkout находит intent по payload, требует состояния `CREATED`, проверяет
user, product, currency, amount, срок и текущую доступность продажи, затем
атомарно переводит intent в `PRECHECKOUT_APPROVED`. Если условие перестало
выполняться, pre-checkout отклоняется. Проверка уменьшает вероятность оплаты при
аварии, но не является гарантией: известный matching intent после одобренного
pre-checkout принимается в durable receipt независимо от последующего состояния
feature flag и нод. Истечение TTL после `PRECHECKOUT_APPROVED` само по себе не
является основанием отвергнуть последующий `successful_payment`.

### Приём и применение успешного платежа

```text
Telegram successful_payment
        |
        v
apps/payments: accept receipt
  - find matching PaymentIntent by random invoice_payload
  - validate user/product/provider/currency/amount
  - atomically mark approved intent PAID
  - INSERT PaymentReceipt, unique(provider, charge_id)
  - return accepted/idempotent
        |
        +--> bot: «Оплата принята, доступ готовится»
        |
        v
queue vpn_payment_fulfillment (concurrency=1)
        |
        v
ApplyPaymentReceiptService transaction
  - claim RECEIVED/RETRY receipt
  - create Payment once
  - injected FulfillVPNPurchaseService
  - create/extend VPNAccess
  - create VPNPurchase(payment, access)
  - mark receipt APPLIED
        |
        v after commit
schedule desired credential delivery
```

Повтор одного `(provider, charge_id)` возвращает состояние существующего
receipt. Если user, product, currency, amount или immutable provider data не
совпадают, запрос отклоняется как `PaymentIdentityConflict` и создаётся
дедуплицированный административный alert. Он никогда не продлевает срок второй
раз.

После события `successful_payment` текущие feature flag, цена, активность
товара, TTL уже одобренного intent и состояние нод больше не являются причинами
отклонить receipt. Endpoint принимает только известный matching intent и
проверяет immutable данные самого платежа; выключение продаж не теряет оплату.

Срок рассчитывается внутри единственной fulfillment-транзакции:

```text
new_expired_at = max(current_expired_at, receipt.accepted_at) + 30 days
```

`accepted_at` — серверное время первого durable сохранения receipt. Текущий bot
contract не передаёт надёжный provider `paid_at`, поэтому message timestamp не
используется как момент покупки.

Для первой покупки создаются стабильный subscription token, desired UUID и
revision 1. Повторная покупка меняет только срок; token, desired UUID и
опубликованный UUID сохраняются. Изменения регистрируют delivery после commit,
поэтому отправка в Telegram или HTTP-ошибка ноды не откатывают оплату.

### Single-writer и SQLite

`select_for_update()` не используется как гарантия конкурентности: SQLite не
предоставляет нужную row-lock семантику. Все VPN receipts обрабатывает отдельная
Celery queue `vpn_payment_fulfillment`, которую default worker не слушает.
Единственный Compose-service запускается с
`-Q vpn_payment_fulfillment --concurrency=1 --prefetch-multiplier=1`; default
worker явно ограничен своими очередями.

Перед claim и на всё время receipt-transaction singleton worker дополнительно
держит host-level exclusive `flock` на файле рядом с общей SQLite DB, например
`/app/data/vpn-payment-writer.lock`. Все версии singleton service монтируют один
и тот же host data directory, поэтому дублирующий или rolling container не может
одновременно применить receipt. Rollout сначала останавливает/заменяет старый
singleton и только затем запускает новый; readiness нового worker включает
успешное получение lock. Только `ApplyPaymentReceiptService` может превратить
receipt в `Payment` и изменить оплаченный срок VPNAccess.

Уникальный receipt остаётся последней защитой от двух API deliveries. Короткие
SQLite `OperationalError: database is locked` обрабатываются ограниченным retry
с jitter, не повторяя уже завершённый receipt. Административная деактивация и
reissue не меняют оплаченный срок; они используют атомарные conditional updates
по `state_revision`, поэтому не полагаются на `select_for_update()` и не могут
затереть конкурентный fulfillment.

Celery Beat периодически выбирает `RECEIVED`, наступившие `RETRY` и stale
`PROCESSING` receipts, возвращает stale lease в `RETRY` и повторно ставит их в
single-writer queue. Поля lease (`processing_started_at`, `lease_id`) позволяют
воркеру завершить только захваченную им попытку. Ошибка broker после DB commit
не теряет работу: receipt остаётся выбираемым Beat recovery. После исчерпания
обычных попыток состояние остаётся `RETRY` с увеличенным backoff и alert, а не
становится необслуживаемым terminal failure без решения оператора.

### Доставка credential и готовность

У `VPNAccess` разделены:

- `desired_uuid`/`desired_revision` — текущее желаемое состояние БД;
- `published_uuid`/`published_revision` — последняя revision, подтверждённо
  применённая хотя бы на одной ноде и разрешённая к выдаче клиенту.

При первой покупке `published_uuid` отсутствует, поэтому URL пользователю ещё
не отправляется. Успешный ответ агента на exact snapshot фиксируется в
`VPNAccessNodeApply`. Когда хотя бы одна доступная нода подтверждает текущую
desired revision, сервис атомарно публикует её. Только после этого ставится
durable задача уведомления с URL.

Публикация revision и факт отправки уведомления разделены. Beat выбирает READY
доступы, у которых `ready_notification_revision < published_revision`, и
повторно ставит notification task. Marker обновляется только после успешного
ответа Telegram. Поэтому потеря broker enqueue после commit или ошибка Telegram
не подавляет будущую отправку. Возможный сбой между успешной Telegram-отправкой
и записью marker даёт повторное уведомление, но не потерю URL; доставка имеет
at-least-once семантику.

Reissue создаёт новый `desired_uuid` и увеличивает revision, не меняя token или
срок. До первого подтверждения subscription endpoint продолжает отдавать
предыдущий `published_uuid`, поэтому стабильная URL не становится временно
нерабочей. После первого подтверждения публикуется новый UUID. Остальные ноды
получают его асинхронно; нода с ошибкой исключается из новой подписки до
успешного reconcile. Повторный reissue во время незавершённого reissue
отклоняется `409 VPNReissueInProgress`; новый UUID не создаётся.

Готовность reissue после одной ноды не обещает мгновенного отзыва старого UUID
на недоступной management-plane ноде: ранее загруженная конфигурация может
работать там до восстановления reconcile. Такой revision drift наблюдается и
алертится; оператор изолирует публичный listener длительно отставшей ноды по
runbook. Полный отзыв на всём fleet имеет eventual, а не синхронную семантику.

Первая готовность и готовность reissue означают «актуальная revision применена
хотя бы на одной выдаваемой ноде», а не «весь fleet синхронизирован».

### Subscription URL

URL имеет вид `GET /api/v1/vpn/subscriptions/<token>/`; token генерируется через
`secrets` и содержит не менее 256 бит энтропии. Token создаётся один раз и не
меняется при продлении или reissue.

Ответ для активного READY-доступа — `200 text/plain; charset=utf-8`, Base64 от
UTF-8 списка с одним percent-encoded `vless://` URI на строку. URI строит один
доменный generator, а порядок задаёт `VPNNode.number`. В список попадают только
активные, разрешённые и `READY` ноды, для которых подтверждена
`published_revision` этого доступа.

Профиль MVP фиксирован и не допускает transport negotiation:

```text
vless://<published_uuid>@<host>:<port>?encryption=none&flow=xtls-rprx-vision&security=reality&sni=<sni>&fp=chrome&pbk=<public-key>&sid=<short-id>&type=tcp#<location>
```

Authority корректно обрамляет IPv6 квадратными скобками; все query values и
fragment кодируются стандартным URL encoder. Приватный REALITY key и target в
URI не попадают.

Если initial access ещё не опубликован, endpoint возвращает `503` с
`Retry-After`, но URL не отправляется пользователю. Истёкший или
административно деактивированный доступ возвращает `200` с Base64 пустой строки;
неизвестный token — `404`. Все ответы содержат `Cache-Control: private,
no-store`, `X-Content-Type-Options: nosniff` и не запускают provision или запись
в БД.

## Модель данных

Все новые модели наследуются от `BaseDjangoModel`; активные строки выбираются
через `.active()`.

### ERD

```text
SystemUser 1 ---- 0..1 VPNAccess
                         |
                         +---- * VPNPurchase * ---- 1 Payment
                         |
                         +---- * VPNAccessNodeApply * ---- 1 VPNNode

Product 1 ---- * PaymentReceipt 0..1 ---- 1 Payment
Product 1 ---- * Payment
Product 1 ---- * PaymentIntent 1 ---- 0..1 PaymentReceipt

VPNNode 1 ---- * VPNAccessNodeApply
```

### `Product` и `Payment`

`Product.code` получает стабильные значения `mtproto_30d` и `vless_30d`.
На expand-этапе поле nullable; условная уникальность действует только для
непустого code. Новый код всегда ищет товар по code и не использует `.first()`.

`Payment.product` — nullable `ForeignKey(Product, PROTECT)` на expand-этапе.
Новые payment paths обязаны заполнять его; null разрешён только legacy writers и
данным во время rollback window. Существующий `Payment.key` остаётся nullable
`OneToOneField` без изменения schema или reverse contract: VPN payment имеет
`key=None`, а связь с VPNAccess находится в `VPNPurchase`. Общая условная уникальность
`(provider, charge_id)` применяется только к непустым charge IDs.

Связь VPN не добавляется в `Payment`: `apps/payments` не должен импортировать
VPN model. Её хранит `VPNPurchase` в `apps/vpn`.

### `PaymentIntent`

- `user`, `product`;
- unique `invoice_payload`, случайный token минимум 256 бит;
- immutable `currency`, `amount` и provider kind;
- `expires_at` с коротким настраиваемым TTL;
- `status`: `CREATED`, `PRECHECKOUT_APPROVED`, `PAID`, `EXPIRED`, `CANCELLED`;
- nullable OneToOne `receipt` после successful payment.

Intent не резервирует VPNAccess и не продлевает срок. `CREATED` после TTL больше
не проходит pre-checkout и может быть переведён Beat в `EXPIRED`.
`PRECHECKOUT_APPROVED` не переводится в `EXPIRED` и может быть принят matching
successful payment после TTL, flag-off или потери READY-нод. Повтор
pre-checkout/payment идемпотентен только при полном совпадении immutable полей.

### `PaymentReceipt`

- `user`, `product`;
- `provider`, `charge_id` с unique `(provider, charge_id)`;
- immutable `accepted_at`, `currency`, `amount`, связь с `PaymentIntent`;
- `status`: `RECEIVED`, `PROCESSING`, `RETRY`, `APPLIED`;
- `attempt_count`, `next_attempt_at`, `processing_started_at`, `lease_id`;
- masked `last_error_code`, без provider payload и секретов;
- nullable OneToOne `payment` после успешного применения.

Пустой `charge_id` для новых запросов запрещён. Raw provider payload не
сохраняется и не логируется; сохраняются только поля, нужные для проверки
identity и аудита суммы.

### `VPNAccess`

- `user` — unique OneToOne к `SystemUser`;
- `subscription_token` — unique, минимум 256 бит энтропии;
- `desired_uuid`, `desired_revision`;
- nullable `published_uuid`, `published_revision`;
- `expired_at` — timezone-aware;
- `state`: `PREPARING`, `READY`, `EXPIRED`, `DISABLED_REFUND`;
- `state_revision` для optimistic conditional updates;
- `ready_notification_revision` как marker последней успешно отправленной URL;
- nullable `disabled_at`, `disabled_reason`, `disabled_by` для audit возврата.

`is_active=False` используется только для общей административной архивации и не
заменяет доменный state. Доступ клиенту определяется одновременно
`is_active=True`, `state=READY`, `expired_at > now()` и наличием published UUID.

### `VPNPurchase`

- `payment` — unique OneToOne к `Payment`;
- `access` — ForeignKey к `VPNAccess`;
- `period_days=30` и `expired_at_after` как audit результата fulfillment.

Один доступ связан со многими покупками, но один Payment может выполнить не
более одного VPN fulfillment.

### `VPNNode`

- unique `name` и `number`;
- пользовательские `location`, публичные `host`, `port`;
- HTTPS `agent_base_url` host-nginx management endpoint; backend никогда не
  обращается напрямую к контейнерному адресу агента;
- `agent_secret_key` — имя секрета в environment/Ansible, не сам token;
- `agent_contract_version`;
- `health_state`: `NEW`, `SYNCING`, `READY`, `UNHEALTHY`, `INCOMPATIBLE`,
  `OVER_CAPACITY`;
- independent `data_plane_state`: `SERVING_READY`/`UNAVAILABLE`;
- `is_access_available` — ручной допуск новых и существующих выдач;
- `desired_snapshot_revision/hash`, `applied_snapshot_revision/hash`;
- `last_health_at`, `last_error_code`;
- REALITY client parameters: public key, short id, server name, fingerprint,
  flow.

Уникальны `number` и публичный `(host, port)`. Model/admin validation до
сохранения проверяет DNS/IPv4/IPv6 authority, port, X25519 public key, short-id
как hex допустимой длины, SNI как hostname и разрешённые enum fingerprint/flow.
Приватный REALITY key и REALITY target в центральной БД не хранятся.

### `VPNAccessNodeApply`

- legacy unique `(access, node)` current row сохраняет cardinality старого
  runtime и обновляется dual-write;
- `desired_revision`, nullable `applied_revision`;
- `status`: `PENDING`, `APPLIED`, `FAILED`;
- `last_attempt_at`, безопасный `last_error_code`.

Новая expand-only `VPNAccessNodeRevisionEvidence` имеет unique
`(access, node, revision)`, отдельные строки applied/pending/failed и
`is_serving`. Новые readers используют history; reverse migration удаляет её и
`VPNNode.data_plane_state`, не меняя legacy row/table.
During rollback window exact legacy row служит fallback только если history для
published revision отсутствует: так writes старого runtime видны новому,
но наличие history не может быть обойдено legacy-строкой.

## Контракт backend ↔ VPN-agent

Контракт имеет major-версию `v1`. Backend передаёт и проверяет contract version;
health агента возвращает `contract_version`, agent commit SHA, Xray version,
readiness и applied snapshot revision/hash.

Endpoints:

- `GET /api/v1/health` — runtime/Xray readiness и contract version;
- `GET /api/v1/snapshot` — только текущие applied revision/hash/schema;
- `PUT /api/v1/snapshot` с
  `{schema_version, snapshot_revision, snapshot_hash, accesses[]}` — привести
  только выделенный managed inbound к точному snapshot.

Incremental mutation endpoints отсутствуют. Любое добавление, reissue,
истечение, refund deletion или изменение fleet формирует следующую монотонную
exact snapshot revision конкретной ноды. Это исключает гонку позднего
incremental вызова с более новым глобальным snapshot.

Canonical snapshot сортируется по numeric `access_id` и содержит только
активные, неистёкшие, не деактивированные desired credentials. Hash — SHA-256
canonical JSON без transport metadata. Revision монотонна для конкретной ноды.
Агент:

- повтор той же revision/hash обрабатывает как no-op;
- меньшую revision отклоняет `409 stale_revision`;
- ту же revision с другим hash отклоняет `409 revision_conflict` и становится
  not-ready;
- payload больше настроенного лимита entries или bytes отклоняет `413
  snapshot_too_large` до изменения Xray;
- неизвестную major schema/contract version отклоняет `426
  incompatible_contract`.

Backend никогда не разбивает exact snapshot на независимо применяемые partial
snapshots. Он проверяет размер заранее. При overflow нода становится
`OVER_CAPACITY`, исключается из выдачи и создаётся один alert. Новая продажа
разрешена только если хотя бы одна нода вместит prospective snapshot; уже
оплаченный receipt остаётся в recovery и не теряется. Поддержка chunked
snapshot проектируется отдельно, если текущего лимита перестанет хватать.

### Atomic persistence и crash recovery агента

Агент валидирует весь запрос до изменения состояния, применяет exact desired set
только к managed inbound, проверяет принятие Xray и затем пишет локальный
snapshot через temporary file, `fsync` и atomic rename. Только после этого
возвращается success. Локальный файл содержит contract/schema version, revision,
hash и managed accesses с минимальными правами доступа.

Сценарии падения:

- до принятия Xray — старый snapshot остаётся authoritative local cache;
- после изменения Xray, но до atomic rename — после рестарта агент
  восстанавливает последний сохранённый snapshot, остаётся not-ready и ждёт
  повторного reconcile;
- после rename, но до HTTP response — повтор той же revision/hash является
  безопасным no-op.
Повтор exact-current reconcile на центральном backend также не переводит
уже serving evidence в `PENDING`.

При старте агент восстанавливает сохранённый snapshot в Xray, сверяет hash и
переходит только в `recovery-ready`: центральный backend всё равно не включает
ноду в пользовательскую подписку, пока health и reconcile не подтвердят
совпадение с текущим desired snapshot.

## Reconcile, expiration и возврат

Изменение desired credential после commit увеличивает desired revision каждой
затронутой ноды и создаёт per-node exact snapshot tasks с bounded exponential
backoff и jitter. Ошибка одной ноды не блокирует другие.
После исчерпания быстрых retries нода становится `UNHEALTHY`, исключается из
subscription и получает дедуплицированный alert.

Health-check каждые 5 минут проверяет нездоровые и новые ноды. Нода не становится
`READY` по одному health response: сначала выполняется exact full sync, затем
сверяются revision/hash. Периодический full reconcile всех READY-нод не реже
одного раза в час исправляет потерянные tasks и расхождения после рестартов.
Успешный authenticated health, который подтверждает drift, missing snapshot
или recovery-ready, сбрасывает `data_plane_state` и serving evidence; transport
failure не считается доказательством data-plane outage.

Beat-задача истечения переводит доступ в `EXPIRED` атомарным conditional update
и увеличивает desired snapshot revision нод. Даже если enqueue удаления в
broker потерян, следующий periodic reconcile исключит credential из exact
snapshot. Отдельный необратимый `cleanup_enqueued` marker не используется.

Refund deactivation — явный Django admin action над выбранным применённым VPN
payment. Оператор видит user, payment identity и текущий срок, подтверждает
действие; service записывает `DISABLED_REFUND`, audit actor/reason/time и
запускает reconcile. Повтор действия идемпотентен. Он не изменяет MTProto данные
и не выполняет автоматический денежный refund у provider.

## API центрального backend

Все bot endpoints требуют `Bot-Auth-Token`. Единственное исключение — публичная
subscription URL.

- `POST /api/v1/vpn/payment-intents/` — создаёт intent и возвращает invoice DTO
  с random payload либо `404
  VPNProductNotConfigured`, `409 VPNSalesDisabled` или `503
  VPNCapacityUnavailable`;
- `POST /api/v1/vpn/pre-checkout/` — проверяет active/unexpired intent,
  user/payload/currency/amount и sale availability; success `200`, отказ
  `404 PaymentIntentNotFound`, `409 PaymentIntentMismatch`, `409
  PaymentIntentExpired` или `503 VPNCapacityUnavailable`;
- `POST /api/v1/vpn/payments/` — принимает successful payment только для
  matching intent; `202` для нового
  или уже ожидающего receipt, `200` для уже applied; ошибки `400
  BadPaymentData`, `404 PaymentIntentNotFound`, `409 PaymentIntentMismatch`,
  `409 PaymentIdentityConflict`. Feature flag, current Product activity/price,
  intent TTL после approved pre-checkout и состояние нод после факта успешной
  оплаты не блокируют этот endpoint;
- `POST /api/v1/vpn/status/` — `NOT_PURCHASED`, `PREPARING`, `READY`, `EXPIRED`
  или `DISABLED`; URL возвращается только для `READY`;
- `POST /api/v1/vpn/reissue/` — `202 PREPARING`, stable URL не меняется;
  `404 VPNAccessNotFound`, `409 VPNAccessExpired`, `409 VPNReissueInProgress`;
- `GET /api/v1/vpn/subscriptions/<token>/` — публичный контракт, описанный выше.

DRF error DTO для новых endpoints един:
`{"code": "stable_machine_code", "message": "safe user message", "detail": {}}`.
Внутренние ошибки агента, UUID, tokens и payload в `detail` не попадают.

## Безопасность

### Agent channel

Каждая нода имеет отдельный bearer token минимум 256 бит. Token хранится только
в Ansible Vault/environment backend и агента; `VPNNode` содержит лишь lookup key.
Для центрального backend все agent endpoints, включая health, доступны только
через host nginx по HTTPS с обязательной проверкой сертификата и firewall
allowlist исходящего IPv4-адреса backend. Nginx проверяет внешний TLS и
проксирует запрос с исходным bearer token к агенту. Сравнение bearer token в
агенте — constant-time.

Единственное разрешённое plaintext-соединение management plane —
`host nginx -> agent` внутри принадлежащего Compose bridge с `internal: true`.
Это локальный upstream nginx, а не удалённо доступный endpoint на private
address: агент не публикует host ports, не подключается к public/default
network и не имеет иного management listener. Для production Compose сеть
фиксирована полностью:

- subnet `172.31.255.0/28`, gateway `172.31.255.1`;
- Xray `172.31.255.2`;
- agent `172.31.255.3`.

Plain HTTP на host port, внешнем/private интерфейсе, другой Docker-сети или при
любом отклонении от этой топологии запрещён. До создания/старта контейнеров
deploy fail-closed проверяет, что subnet не пересекается с маршрутами и
интерфейсными сетями хоста либо другими Docker networks. Уже существующая
Compose management network допустима только при точном совпадении имени,
`internal`, subnet и gateway; несовпадение считается drift, а не исправляется
неявно. Также preflight проверяет фиксированные container IPv4, отсутствие
публикации портов агента и отсутствие у него дополнительных сетей.

После старта deploy повторно проверяет фактическую Docker network/container
конфигурацию через runtime inspection и с хоста выполняет прямой
аутентифицированный health-запрос к `172.31.255.3` по HTTP. Только после
успешного direct health nginx получает/reloads HTTPS vhost; внешний
аутентифицированный HTTPS health является отдельной финальной проверкой. При
ошибке nginx endpoint не публикуется, а deploy завершается fail-closed.

Ротация token выполняется без разрыва:

1. агент получает `next` token и временно принимает current+next;
2. backend переключается на next и проходит health+reconcile;
3. current удаляется из агента;
4. факт ротации без значений секретов фиксируется в release evidence.

Компрометация одной ноды не даёт credential для других нод. mTLS может быть
добавлен отдельным security change, но не заменяет обязательные HTTPS,
certificate verification и firewall rules MVP.

### REALITY

Приватный REALITY key остаётся только на ноде. REALITY target задаётся в
versioned Ansible-конфигурации агента, а не через Django admin. Разрешены только
оператором проверенные внешние TLS 1.3 targets на 443, не принадлежащие private,
loopback, link-local или metadata ranges. Перед rollout проверяются доступность,
соответствие SNI/сертификата, отсутствие перенаправления во внутреннюю сеть и
правовые/эксплуатационные риски. Target health мониторится; смена target/Xray
параметров проходит как отдельный agent release.

### Subscription URL и логи

Nginx выделяет subscription location и не пишет request URI/token/args в access
log; фиксируются только статический route label, status и latency. HTTP только
перенаправляет на HTTPS с `308`, а Django proxy доступен лишь в HTTPS location.
Django filter редактирует request-derived path/query, включая уже
материализованный `request.GET`, и logging extras; он не логирует
`Bot-Auth-Token`, agent Authorization, invoice provider payload, UUID или
subscription token. Admin показывает token только маскированно.

Публичный endpoint ограничивается atomic Lua Redis throttle по
`SHA-256(token) + SHA-256(trusted source IP)`: по умолчанию 30 запросов в минуту.
TTL устанавливается первым `INCR` в той же операции. Trusted IPv4/IPv6 CIDR и
right-to-left разбор proxy chain исключают подмену `X-Forwarded-For`; edge
перезаписывает входной XFF. Rate-limit возвращает `429`, а недоступный Redis
fail-closed `503`, оба с `Retry-After`. Subscription URL не
передаётся внешней аналитике.

## Feature flag

`VPN_SALES_ENABLED=False` по умолчанию блокирует выдачу invoice и pre-checkout и
скрывает новые sale actions в боте. Он намеренно не влияет на:

- приём уже состоявшегося `successful_payment`;
- single-writer и Beat recovery;
- delivery/reconcile/health/expiration;
- status и subscription endpoints;
- reissue и refund deactivation существующего доступа.

Отдельный ручной `VPNNode.is_access_available` выводит конкретную ноду из
выдачи/новых продаж, но exact reconcile продолжает удаление и обслуживание
состояния. Если все ноды недоступны, новые продажи блокируются, а уже оплаченные
receipts остаются `PREPARING/RETRY` до восстановления.

## Миграции и rollback

Изменения выполняются expand/contract, причём MVP release содержит только
rollback-safe expand:

1. read-only preflight проверяет число/назначение существующих Product,
   непустые дубли `(provider, charge_id)`, orphan Payment/GiftCertificate и
   достаточное место/backup SQLite;
2. preflight требует ровно один active существующий Product; при ином числе
   release останавливается до миграции;
3. добавляются nullable `Product.code`, `Payment.product`; `Payment.key` и его
   OneToOne contract не изменяются;
4. создаются `PaymentIntent`, `PaymentReceipt` и таблицы `apps/vpn`;
5. deterministic data migration присваивает единственному active Product код
   `mtproto_30d` и backfill-ит им применимые legacy Payment; gift payments могут
   ссылаться на тот же `mtproto_30d`, а неоднозначные inactive legacy строки
   остаются с `product=NULL` на rollback window;
6. миграция повторно проверяет дубли и только затем добавляет conditional unique
   constraints для непустых Product.code и payment identity;
7. новый код требует product для всех новых writes, но читает legacy null;
8. `Product(code="vless_30d")` создаётся оператором после deploy через admin.

Preflight не угадывает основной товар: он требует ровно один active Product и
при нуле или нескольких active строках останавливает release, печатая только
PK/code/status без коммерческих или платёжных данных. Inactive неоднозначные
Products не получают invented code и могут остаться nullable. Отдельный
gift-specific Product не создаётся: gift остаётся существующим поведением и
non-goal. Дубли payment identity не объединяются автоматически;
release блокируется до отдельного подтверждённого исправления данных.

`Product.code` и `Payment.product` не становятся NOT NULL в том же release.
Поэтому автоматический rollback на прежний commit продолжает создавать legacy
Payment без product. Contract migration допускается отдельным будущим PR только
после окончания rollback window, подтверждения отсутствия старых writers и
полного backfill. VPN-таблицы при code rollback не удаляются, чтобы не потерять
оплаченные receipts/accesses.

SQLite migration проверяется на копии production-like DB с измерением времени
table rebuild. Перед deploy Litestream/SQLite backup и restore check обязательны;
во время schema migration новые платежные handlers ещё не включены feature
flag.

## Cross-repo release и deploy

Оба репозитория публикуют полный reviewed commit SHA. Release evidence содержит:

- backend SHA и agent SHA;
- agent contract/schema major version;
- pinned Xray version/image digest;
- поддерживаемую backend↔agent compatibility matrix;
- результаты agent contract, Android/iOS import и connection smoke tests.

Первое исправление management transport на direct bridge выпускается в два
неразделимых этапа. Сначала отдельный bootstrap SHA с описанной выше topology
проходит review, CI и test deploy; rollback на более старый loopback SHA для
него явно отключён. Loopback-вариант, где host nginx обращается к опубликованному
на `127.0.0.1` порту контейнера, не считается операционно совместимым rollback
target на Docker 29.6. Затем новый final SHA tracked-изменением объявляет только
проверенный bootstrap SHA совместимым rollback target, снова проходит полный
review, CI и test deploy, откатывается на bootstrap в controlled rehearsal и
разворачивается вперёд на тот же final SHA. Именно final SHA, а не bootstrap,
становится A-010 agent SHA для backend integration.

Каждый этап идентифицируется полным immutable SHA. Любое tracked-изменение после
review или test deploy лишает прежнее evidence статуса evidence текущего head и
требует полного gate для нового SHA; историческое evidence exact bootstrap SHA
сохраняется как доказательство допустимости rollback target. Release evidence
final SHA обязано отдельно содержать bootstrap SHA, успешный rollback rehearsal
и успешный forward redeploy; branch names и плавающие image tags не заменяют ни
один SHA gate.

Backend для MVP принимает только agent contract v1. Несовместимый агент получает
`INCOMPATIBLE`, не участвует в продаже/подписке и не получает mutation calls.
Изменения contract сначала добавляются backward-compatible на agent, затем на
backend; удаление старой версии — только отдельным release после fleet audit.

Последовательность rollout:

1. создать `my-vless-vds-instance`, закрепить Xray и проверить agent contract;
2. развернуть agent/Xray на нодах с закрытым firewall и продажами off;
3. выполнить backend preflight/backup, применить expand migrations и развернуть
   backend/bot с `VPN_SALES_ENABLED=False`;
4. создать VPN Product и VPNNode, проверить TLS, contract, REALITY validation,
   snapshot capacity и initial empty reconcile;
5. подтвердить минимум две READY-ноды в разных пользовательских локациях, затем
   импортировать одну production-like subscription в закреплённые оператором
   поддерживаемые актуальные версии Android- и iOS-клиента, выполнить соединение;
6. запустить sandbox или контролируемую реальную оплату, проверить receipt,
   readiness notification, продление, reissue и refund deactivation;
7. включить продажи.

Deploy каждого репозитория требует отдельного PR review и SHA. Production gate
запрашивает одно явное разрешение на согласованный release pair и перечисляет
оба SHA; это разрешение не переносится на другой pair. Ни один дочерний агент не
выполняет deploy.

Rollback:

- сначала выключить новые продажи;
- backend можно вернуть только на предыдущий VLESS-совместимый SHA без rollback
  expand migrations; действующие receipts/reconcile продолжает обслуживать
  worker из этого совместимого release;
- agent откатывается только на SHA, совместимый с сохранённой snapshot schema,
  текущим backend contract и фактической Docker network topology; snapshot перед
  downgrade сохраняется. Для direct-bridge final SHA таким target является
  проверенный bootstrap SHA, но не более старый loopback SHA;
- для первого VLESS release прежний pre-VLESS SHA не считается совместимым после
  появления оплаченного receipt; если совместимого code rollback нет, остаётся
  текущий runtime с продажами off, пока выпускается forward fix;
- отключение subscription/reconcile уже оплативших пользователей не является
  допустимым rollback.

## Наблюдаемость и alerting

Структурированные метрики/логи без секретов:

- receipts по status, возраст oldest RECEIVED/RETRY, attempts и lease recovery;
- latency от receipt accepted_at до APPLIED и от APPLIED до первой READY revision;
- число PREPARING accesses и ready nodes;
- per-node health, desired/applied revision mismatch и snapshot age;
- delivery/reconcile success/failure, overflow/incompatible counters;
- readiness notification success/failure;
- subscription status/latency/429 без raw token;
- refund deactivation audit.

Alerts дедуплицируются по stable resource/error code. Обязательны alerts на
stale receipt, отсутствие READY-нод, incompatible agent, snapshot overflow,
длительный revision drift, repeated auth/TLS failure и невозможность отправить
ready notification. UUID, URLs, tokens, Authorization и full agent payload в
логах/alerts отсутствуют.

## Failure behavior

| Сбой | Поведение |
|---|---|
| Все ноды down до оплаты | Invoice/pre-checkout блокируются |
| Ноды down после оплаты | Receipt durable, доступ PREPARING, Beat/reconcile продолжают |
| Broker недоступен после receipt commit | Beat позже переочередит receipt |
| Worker умер в PROCESSING | Lease устареет, Beat вернёт receipt в RETRY |
| Два singleton containers запущены одновременно | Только владелец host `flock` применяет receipts; второй not-ready |
| Повтор successful payment | Existing receipt/result, срок не меняется |
| Одна нода не применила UUID | Нода исключена, другие продолжают; recovery full sync |
| Agent ответ потерян после snapshot apply | Retry той же revision/hash — no-op |
| Snapshot partial/crash | Агент not-ready, восстанавливает atomic local snapshot, затем reconcile |
| Snapshot превышает лимит | Нода OVER_CAPACITY, partial apply запрещён, alert |
| Несовместимая версия agent | Нода INCOMPATIBLE и не участвует в продаже |
| Ready notification не ушло | Доступ остаётся READY, Beat повторяет at-least-once доставку |
| Access истёк/деактивирован | URL выдаёт пустую подписку, exact reconcile удаляет UUID |
| Feature flag off | Только новые invoice/pre-checkout блокируются |

## Стратегия тестирования

Разработка обеих delivery units идёт через TDD существующими framework.

### Backend unit/integration

- Product lookup только по code; sale availability и обе цены;
- expand migration и rollback старого writer на production-like SQLite copy;
- preflight 0/1/N products, duplicate/blank payment identities;
- intent TTL/state/mismatch, approval-before-expiry и payment-after-approved-expiry;
- receipt identity collision, API duplicate и recovery lease;
- два параллельных delivery одного charge дают одно продление;
- два разных receipts single-writer дают последовательные +30 дней;
- dedicated queue routing, prefetch=1, duplicate-container host lock и SQLite
  retry без двойного fulfillment;
- `max(expired_at, accepted_at) + 30 days` для active/expired;
- notification только после первой current revision snapshot apply;
- Beat восстанавливает потерянный notification enqueue; marker только после send;
- stable token при renewal/reissue, old published UUID до readiness;
- refund deactivation и отсутствие изменений MTProto/referral/gift state;
- all-nodes-down invoice/pre-checkout block, successful-payment bypass flag/down;
- expiration и reconcile восстанавливаются без fragile enqueue marker;
- service factories соблюдают DI и import graph не содержит payments→vpn.

### API/bot

- `Bot-Auth-Token` на всех bot endpoints;
- payload/currency/amount validation для RUB и Stars;
- точные HTTP status и stable error DTO;
- состояния NOT_PURCHASED/PREPARING/READY/EXPIRED/DISABLED;
- bot немедленно подтверждает receipt и отдельно отправляет URL при readiness;
- feature flag не ломает existing status/subscription/reissue;
- Base64/URI percent encoding, IPv6 authority, порядок и фильтрация нод;
- unknown/preparing/expired/disabled token responses и no-store headers;
- Nginx/Django logging redaction, trusted-IP Redis throttle и `429`.

### Agent/contract

- отсутствие incremental mutation endpoints;
- exact snapshot add/replace/remove только managed inbound;
- canonical hash и правила stale/conflicting revision;
- reject invalid/oversize payload до Xray mutation;
- atomic file persistence и три crash points;
- restart restore до ready, Xray API error и pinned-version compatibility;
- HTTPS auth, per-node token isolation и staged rotation;
- backend consumer-driven contract tests запускаются также в agent CI.

### Release evidence

- полный `make test` backend и полный suite агента;
- production Compose/Ansible syntax checks обоих репозиториев;
- backup/restore и migration duration evidence;
- exact compatibility pair SHA;
- production-like Android/iOS import и реальное соединение;
- smoke: invoice, payment, delayed readiness, renewal, reissue, node recovery,
  refund deactivation и flag off.

## Документация

При реализации обновляются `docs/BUSINESS.md`, `docs/ARCHITECTURE.md`,
`docs/CONTRACTS.md`, `docs/MODELS.md`, `docs/apps/PAYMENTS.md`; добавляются
`docs/apps/VPN.md`, agent API/deploy/runbook в `my-vless-vds-instance` и
cross-repo release checklist. Конкретные коммерческие цены и секреты в git не
фиксируются.

## Трассировка требований

| Требования | Архитектурное покрытие |
|---|---|
| BR-001, BR-004, BR-017; AC-001, AC-012 | Отдельные `apps/vpn`, product code, bot section; отсутствие изменения MTProto |
| BR-002, BR-009, BR-012; AC-006, AC-007, AC-008 | Durable receipt, single writer, unique identity, формула срока |
| BR-003, BR-018; AC-002, AC-013 | Product prices, RUB/Stars invoice validation |
| BR-005, BR-006, BR-007, BR-008; AC-003, AC-004 | Immediate receipt ack, async delivery, published revision и readiness notification |
| BR-010, BR-011; AC-006, AC-007, AC-009 | Stable token, desired/published UUID revisions |
| BR-013, BR-014; AC-005 | Двойная availability check; accepted receipt не зависит от нод |
| BR-015; AC-010 | Ограниченная семантика `VPN_SALES_ENABLED` |
| BR-016; AC-011 | Audited idempotent refund deactivation и exact removal |

## Архитектурный gate

Архитектура закрывает утверждённые BR/AC без изменения non-goals. До
implementation обязательны два согласованных плана: центральный backend+bot и
`my-vless-vds-instance`, с checkpoint на agent contract v1, compatibility pair,
миграционный preflight и порядок rollout. Реализация не начинается, пока оба
плана не прошли архитектурное ревью.
