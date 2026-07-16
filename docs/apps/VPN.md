# Приложение VPN

`apps/vpn` владеет центральным desired state VLESS VPN: пользовательскими
доступами, аудитом покупок, публичными параметрами нод и evidence применения
credential revision. База Django является source of truth; состояние Xray на
нодах производно.

## VPNAccess

У пользователя может быть не более одного `VPNAccess`. Персональный
`subscription_token` генерируется из 256 случайных бит при первой покупке и не
меняется при продлении или reissue. Поля `desired_uuid`/`desired_revision`
описывают желаемый credential, а nullable
`published_uuid`/`published_revision` — последнюю revision, подтверждённую хотя
бы одной доступной нодой.

Состояния:

| State | Значение |
|---|---|
| `PREPARING` | Initial delivery или reissue ещё не подтверждён |
| `READY` | Опубликованный UUID/revision точно совпадают с desired credential |
| `EXPIRED` | Оплаченный срок истёк |
| `DISABLED_REFUND` | Доступ отключён после возврата |

`state_revision` используется для optimistic conditional updates.
`ready_notification_revision` не может опережать опубликованную revision.
Возврат требует audit-полей `disabled_at`, `disabled_reason`, `disabled_by`.
Общее `is_active` предназначено только для архивации и не заменяет state.
Во время staged reissue состояние `PREPARING` разрешает сохранить предыдущую
published пару, пока новые desired UUID/revision ещё доставляются. При любом
state равная desired/published revision требует равенства UUID; старый UUID
разрешён только когда published revision строго меньше desired. Null published
pair остаётся допустимой до первой публикации. `READY` дополнительно требует
exact current UUID/revision и не допускает staged pair.

Admin никогда не показывает raw subscription token: отображаются только первые
шесть и последние четыре символа.

## VPNPurchase

`VPNPurchase` связывает один применённый `Payment` с `VPNAccess` и хранит
неизменяемый audit результата fulfillment: `period_days` (по умолчанию 30) и
`expired_at_after`. One-to-one связь с Payment не допускает повторного
применения одного платежа. Связи защищены от удаления через `PROTECT`.

## Fulfillment оплаченного периода

`FulfillPurchaseService` реализует payment-owned
`VPNPaymentFulfillment` и вызывается внутри транзакции
`ApplyPaymentReceiptService`. Первая покупка создаёт единственный `VPNAccess`
со сроком `accepted_at + 30 days`. Продление всегда использует формулу
`max(current_expired_at, accepted_at) + 30 days`: активный период получает ровно
30 дней сверху, истёкший начинается от серверного времени принятия durable
receipt и возвращается в `PREPARING`.

Продление не меняет `subscription_token`, `desired_uuid` или MTProto/free/gift/
referral state. `VPNPurchase(payment OneToOne)` является immutable audit и
делает exact повтор того же Payment идемпотентным. Создание/обновление access и
создание purchase входят в payment-owned transaction, поэтому ошибка audit
insert откатывает их вместе с Payment и receipt lease.

Composition root находится в `apps.vpn.factories.payment_receipts`: допустимое
направление импорта — `vpn -> payments`. Он инъектирует concrete fulfillment в
payment orchestrator. Delivery scheduler передаётся контрактом и регистрируется
только after commit; его отказ не отменяет покупку, поскольку periodic reconcile
остаётся durable recovery.

Runnable consumer также принадлежит `apps.vpn`. Тонкая задача
`apps.vpn.apply_payment_receipt` маршрутизируется только в очередь
`vpn_payment_fulfillment`; отдельный Compose worker запускается с concurrency и
prefetch 1 и монтирует общий `./data`. Перед claim и до конца receipt transaction
он удерживает non-blocking exclusive `flock` файла
`/app/data/vpn-payment-writer.lock`. Default worker явно слушает только очередь
`celery`, поэтому concrete fulfillment не может выполняться конкурентно там.

До запуска Celery wrapper отдельно получает lifetime owner lock
`/app/data/vpn-payment-worker.owner.lock` и сохраняет PID владельца. Второй idle
worker не может начать слушать очередь и завершается. Healthcheck проверяет live
PID, command identity dedicated queue и то, что lifetime lock действительно
занят; transaction lock он не получает, поэтому активное применение receipt не
делает законного владельца unhealthy. При выходе worker ОС освобождает оба lock.

Celery Beat раз в минуту вызывает vpn-owned recovery service. Он ограниченной
партией выбирает через payment selector `RECEIVED`, наступившие `RETRY` и stale
`PROCESSING`, условно освобождает stale lease и ставит receipt в singleton queue
с jitter до пяти секунд. Ошибка broker не меняет durable receipt: следующая
итерация Beat снова выберет его. Deploy останавливает старый singleton до запуска
нового и ждёт healthcheck lifetime-владельца.

## VPNNode

Нода хранит публичный authority (`host`, `port`), HTTPS management origin,
версию agent contract, health/capacity state, snapshot revision/hash и только
публичные REALITY client parameters. `number` задаёт стабильный порядок.
Уникальны `name`, `number` и пара `(host, port)`.

`health_state`: `NEW`, `SYNCING`, `READY`, `UNHEALTHY`, `INCOMPATIBLE`,
`OVER_CAPACITY`. Флаг `is_access_available` вручную исключает ноду из новых и
существующих выдач, не отменяя reconcile.

Перед сохранением model/admin validation проверяет:

- DNS, IPv4 или unbracketed IPv6 в `host`, порт 1–65535;
- HTTPS origin агента без credentials, query, fragment и path;
- `agent_secret_key` как environment/Ansible lookup key, а не bearer token;
- X25519 public key как canonical unpadded URL-safe Base64 от 32 байт, только с
  alphabet `A-Za-z0-9_-` (стандартные Base64 `+` и `/` запрещены);
- непустой even-length hex short ID длиной не более 16;
- DNS hostname для SNI;
- фиксированные MVP fingerprint `chrome` и flow `xtls-rprx-vision`;
- согласованность snapshot revision/hash и отсутствие applied revision впереди
  desired revision; для `READY` — exact nonzero equality desired/applied
  revisions и непустых hashes.

Selector READY-нод повторяет exact-sync условия на уровне ORM. Не-READY нода
может иметь новый desired snapshot и предыдущий applied snapshot во время
staged reconcile.

Приватный REALITY key, REALITY target и bearer token агента в центральной БД не
хранятся. Admin-form явно отклоняет попытку передать private key или target.

## HTTPS transport агента

`VPNAgentTransport` — frozen infrastructure dependency с инъектированными
`requests.Session`, timeout-конфигурацией и resolver секрета. Для каждого
запроса resolver заново читает token по `VPNNode.agent_secret_key`: token не
кэшируется в DTO или модели, ноды не делят credential, а переключение
environment current → next начинает действовать без перезапуска transport.

Transport принимает только точный HTTPS origin без trailing slash,
credentials/path/query/fragment; explicit port разрешён. Он всегда передаёт
`verify=True`, connect/read timeout, bearer header и
`X-Agent-Contract-Version`. Redirects отключены для GET и PUT: любой 3xx
становится безопасной protocol error, а snapshot не пересылается на новый
origin. Plaintext fallback отсутствует.

Перед каждым PUT transport выполняет authenticated health preflight и сверяет
contract/schema вместе с reviewed release identity. Для A-010 gate это agent
SHA `20ae654fc460163fe80aa82051ea9bb22f6d664a`, Xray `26.7.11` и digest
`sha256:a1644183accdb0b5be967093fe34be756fd5de15fe2ee0206e842ae17350967f`.
Любое отличие или ответ `426` запрещает mutation. Смена разрешённой release pair
является явным versioned config change после review/test deploy, а не
автоматическим принятием нового health.

Ответ читается stream-ом не более `VPN_AGENT_MAX_RESPONSE_BYTES` (default 64
KiB), независимо от наличия или правдивости `Content-Length`. Success и error
принимают только `application/json` с необязательным UTF-8 charset. Missing/
wrong content type, invalid JSON и overflow становятся redacted protocol error.
`401`, `409 stale_revision`, `409 revision_conflict`, `413
snapshot_too_large`, `426`, timeout и TLS failure преобразуются в фиксированные
infra error codes. Remote body, Authorization, UUID и resolver exception не
входят в error message/context или exception chain.

Настройки: `VPN_AGENT_CONNECT_TIMEOUT_SECONDS`,
`VPN_AGENT_READ_TIMEOUT_SECONDS`, `VPN_AGENT_SNAPSHOT_SCHEMA_VERSION`,
`VPN_AGENT_EXPECTED_SHA`, `VPN_AGENT_EXPECTED_XRAY_VERSION`,
`VPN_AGENT_EXPECTED_XRAY_IMAGE_DIGEST`, `VPN_AGENT_MAX_RESPONSE_BYTES`. Token
задаётся отдельной environment/Ansible переменной с именем из `agent_secret_key`;
значение не документируется и не коммитится.

## Canonical exact snapshot

Selector snapshot выбирает только `is_active`, неистёкшие, не отключённые
`PREPARING`/`READY` accesses и передаёт desired UUID/revision. Published UUID,
subscription token, customer id и другие private/transport поля в payload не
попадают. Истечение, refund и архивирование представлены отсутствием access в
следующем полном snapshot; incremental/chunk mutation не формируется.

`BuildVPNSnapshotService` сортирует доступы по numeric `access_id`, сериализует
hash input как UTF-8 JSON с recursive lexicographic keys и compact separators,
без BOM/newline, и вычисляет lowercase SHA-256. Результат byte-identical общим
contract v1 fixtures. `ForecastVPNSnapshotCapacityService` тем же алгоритмом
считает точные entries и canonical bytes до HTTP. Prospective credential того
же customer заменяет текущий элемент (renew/reissue = `+0`), а новый customer
добавляет один; оба лимита проверяются включительно на границе.

## VPNAccessNodeApply

Строка `(access, node)` уникальна и служит evidence доставки конкретной desired
revision. Статусы: `PENDING`, `APPLIED`, `FAILED`. Для `APPLIED`
`applied_revision` обязана точно совпадать с `desired_revision`; безопасный
`last_error_code` не должен содержать payload или секреты.

## Reconcile, readiness и доставка URL

Каждая активная нода имеет собственную монотонную snapshot revision. Reconcile
строит полный exact snapshot. Если уже сохранённые desired revision/hash
совпадают с построенным snapshot, потерянная Celery-задача повторно доставляет
ту же revision; при изменении desired set revision увеличивается conditional
update-ом без `select_for_update()`. Ограниченные повторные попытки с jitter
разрешают гонку нескольких планировщиков, а ежечасный полный reconcile
восстанавливает потерянный enqueue.

Успешная фиксация полного snapshot атомарно связывает node READY и apply
evidence с его точным составом: все отсутствующие в snapshot строки
`VPNAccessNodeApply` деактивируются и теряют `applied_revision`, включая empty
snapshot. При следующем появлении того же UUID/revision строка сначала снова
становится `PENDING` и не может быть использована для публикации до нового
успешного PUT. До успешного exact removal прежняя published пара и apply
evidence не стираются, поэтому неудачная попытка удаления не выдаёт ложный
отзыв уже опубликованного credential.

Нода становится `READY` только после успешного `PUT` и отдельного post-apply
health, который сообщает точное совпадение revision/hash и readiness `READY`.
Обычный пяти-минутный health check никогда не повышает ноду в `READY` и не
переписывает applied evidence. `RECOVERY_READY` переводит ноду в `SYNCING` и
требует следующий полный `PUT`. Несовместимый contract и overflow дают
`INCOMPATIBLE` и `OVER_CAPACITY`; stale/conflict/transport failure сохраняются
как безопасные redacted `last_error_code`. Ошибка одной ноды не прерывает обход
остального fleet.

После exact apply строки `VPNAccessNodeApply` текущей credential revision
становятся `APPLIED`. `PublishVPNReadinessService` одним conditional update-ом
переводит `PREPARING` в `READY` и копирует desired UUID/revision в published
только при наличии хотя бы одной активной, разрешённой, exact-synced READY-ноды.
Health без apply evidence публикацию не разрешает.

Health tick сохраняет последний reconcile error при `RECOVERY_READY`, drift и
для ноды, которая ещё не подтверждена reconcile как READY; это не сбрасывает
дедупликацию одинакового алерта. Неожиданная ошибка builder/DB/programming
помечает ноду безопасным кодом `unexpected_reconcile_error`, обход продолжает
остальные ноды, после чего fleet-задача завершается ошибкой без логирования raw
exception text.
Health fleet применяет тот же fail-loud принцип с отдельным bounded кодом
`unexpected_health_error`: ожидаемая transport-ошибка остаётся изолированной,
а programming/DB failure после обхода остальных нод завершает health-задачу
безопасным исключением.

Уведомление со стабильным subscription URL отделено от публикации. Marker
`ready_notification_revision` обновляется только после успешного ответа
Telegram. Beat раз в минуту повторно ставит READY-доступы с отстающим marker,
поэтому ошибка broker или Telegram не теряет URL. Сбой между отправкой и записью
marker может дать безопасный дубль: доставка намеренно at-least-once. В логи не
передаются bearer token, subscription URL или snapshot payload.

## Selectors

ORM-чтения сосредоточены в `selectors.py`: lookup активного доступа по user или
subscription token, выбор READY/available нод и evidence конкретного доступа.
Бизнес-сервисы не должны размещать собственные ORM-запросы.

## Доступность новых продаж

`CheckVPNSaleAvailabilityService` работает fail closed: требует включённый
feature flag и хотя бы одну активную, разрешённую, exact-synced READY-ноду с
ожидаемой major-версией agent contract. Capacity forecast считает все активные
неистёкшие `PREPARING`/`READY` accesses. Первая покупка и реактивация истёкшего
доступа прогнозируют `+1`, а продление уже занимающего snapshot access — `+0`.
Для contract v1 лимит 5000 entries является более строгим, чем byte limit
фиксированного access DTO, поэтому переполнение отклоняется до invoice без
блокировки допустимого renewal.

## Миграция и rollback

`vpn.0001_initial` — additive expand migration, зависящая только от payment
expand `0006_vless_payment_expand`, поэтому не связана с параллельным созданием
PaymentIntent/PaymentReceipt. При rollback к коду без VPN таблицы сохраняются:
их удаление не является частью автоматического rollback, чтобы не потерять
покупки и доступы.
