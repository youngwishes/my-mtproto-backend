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
остаётся durable recovery. Runnable task/очередь появляются отдельно в B-009.

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

## VPNAccessNodeApply

Строка `(access, node)` уникальна и служит evidence доставки конкретной desired
revision. Статусы: `PENDING`, `APPLIED`, `FAILED`. Для `APPLIED`
`applied_revision` обязана точно совпадать с `desired_revision`; безопасный
`last_error_code` не должен содержать payload или секреты.

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
