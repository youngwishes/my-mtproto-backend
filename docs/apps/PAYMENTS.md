# Payments

## Зона ответственности

Обработка платежей через ЮKassa и Telegram Stars. Фиксирует факт оплаты,
определяет стратегию (продлить существующий ключ или выдать новый), создаёт
подарочные сертификаты и уведомляет пользователя.

## Ключевые модели

- **Product** — товар для Telegram Payments API. Хранит стабильный nullable-код
  (`mtproto_30d` или `vless_30d`), цену в рублях и в Stars, данные провайдера
  (чек для ЮKassa). Непустой код условно уникален; бизнес-логика ищет товар
  только по коду.
- **Payment** — запись об оплате. Связывает пользователя, nullable Product,
  legacy MTProto-ключ, charge_id, провайдер и тип платежа (`SUBSCRIPTION` или
  `GIFT_CERTIFICATE`). Непустая пара `(provider, charge_id)` условно уникальна
  независимо от типа платежа.
- **GiftCertificate** — одноразовый код `KEY-XXXX-XXXX` на 30 дней подписки. Покупается отдельно от подписки, действует 1 год до активации, после активации хранит получателя и дату активации.
- **PaymentIntent** — короткоживущее durable-намерение на оплату с уникальным
  случайным `invoice_payload`: ровно 64 lowercase hex-символа (256 бит
  энтропии). Пользователь, Product, сумма, валюта, provider, payload и срок
  действия неизменяемы после создания.
- **PaymentReceipt** — durable-квитанция успешного платежа с уникальной парой
  `(provider, charge_id)`. Хранит только проверяемые поля identity и аудита,
  состояние retry/lease и nullable-связь с применённым Payment; raw provider
  payload не сохраняется.

## PaymentIntent state machine

| Состояние | Допустимый следующий статус | Семантика |
|---|---|---|
| `CREATED` | `PRECHECKOUT_APPROVED`, `EXPIRED`, `CANCELLED` | После `expires_at` pre-checkout и successful payment не принимаются. |
| `PRECHECKOUT_APPROVED` (`APPROVED`) | `PAID` | TTL, выключение продаж и потеря нод больше не блокируют matching successful payment. |
| `PAID` | — | Intent связан не более чем с одной durable-квитанцией. |
| `EXPIRED` | — | Terminal-состояние не одобренного вовремя intent. |
| `CANCELLED` | — | Terminal-состояние отменённого до оплаты intent. |

## PaymentReceipt state machine

| Состояние | Допустимый следующий статус | Семантика |
|---|---|---|
| `RECEIVED` | `PROCESSING` | Платёж принят и выбирается recovery независимо от состояния broker/нод. |
| `PROCESSING` | `APPLIED`, `RETRY` | Всегда содержит одновременно `lease_id` и `processing_started_at`; завершить обработку может только владелец exact актуального lease. |
| `RETRY` | `PROCESSING` | Не содержит lease и всегда содержит `next_attempt_at`; число попыток и безопасный `last_error_code` сохраняются. |
| `APPLIED` | — | Nullable ранее `payment` заполнен применённым Payment; повтор не создаёт новую покупку. |

Beat recovery выбирает все `RECEIVED`, наступившие `RETRY` и `PROCESSING` со
старым `processing_started_at`. Stale recovery атомарно очищает старый lease и
переводит receipt в `RETRY`; умерший или запоздавший worker после этого не может
завершить обработку со старым `lease_id`.

Изменяемые state/lease/retry/payment-поля записываются только через conditional
domain API. Обычные model `save()`, QuerySet `update()` и `bulk_update()` не
могут обходить state machine или менять immutable identity. DB constraints
дополнительно запрещают несогласованные PROCESSING/RETRY/APPLIED строки.

Exact повтор `(provider, charge_id)` считается
идемпотентным только при совпадении intent, пользователя, Product, валюты, суммы
и provider identity. Любое отличие при той же identity —
`PaymentIdentityConflict`; такая доставка не применяется повторно.
Перед созданием receipt проверяется identity не только в PaymentReceipt, но и в
legacy `Payment`: существующий не связанный receipt-ом Payment считается явным
collision, потому что legacy-схема не хранит достаточно immutable данных для
безопасного доказательства exact replay. При применении receipt nullable-связь
с Payment заполняется только если provider/charge/user/product совпадают.

## Сервисы

- **CreatePaymentService** — оркестратор платежа. Ищет пользователя, определяет стратегию (extend/issue), создаёт Payment, отправляет уведомление через SendNotificationService.
- **ExtendKeyService** — продлевает срок действия существующего ключа на SUBSCRIPTION_PERIOD_DAYS.
- **CreateGiftCertificateService** — фиксирует успешную оплату подарочного сертификата и создаёт одноразовый код без продления подписки покупателя. Повторная обработка того же платежа идемпотентно возвращает существующий код.
- **ActivateGiftCertificateService** — активирует валидный сертификат: продлевает активный ключ получателя на 30 дней или выдаёт новый ключ на 30 дней.

## Зависимости

Зависит от: core (декораторы, исключения), users (поиск пользователя), vds (выдача/продление ключей), notifications (уведомление об оплате).
От него зависят: бот (вызывает API после успешного платежа и при активации сертификата).

## VLESS expand migration и preflight

Перед expand-миграцией оператор восстанавливает проверяемую SQLite backup-копию
и запускает read-only команду:

```bash
python manage.py vless_migration_preflight --backup-path /path/to/restored.sqlite3
```

Release останавливается, если активных Product не ровно один, существуют
дублированные непустые payment identity, orphan FK, backup не является читаемой
целостной SQLite БД или для table rebuild свободно меньше двух размеров текущей
БД (и абсолютного минимума 8 MiB). Диагностика печатает только PK, code/status и
имя таблицы; title, цены, charge_id, provider data и путь backup не выводятся.
Команда ничего не исправляет: неоднозначные данные разрешаются отдельно и
вручную до повторного запуска.

Миграция присваивает единственному активному legacy Product код `mtproto_30d` и
связывает с ним существующие Payment. Inactive Product остаются с `code=NULL`.
На чистой БД без Product миграция допустима, но production preflight всё равно
блокирует такой rollout. `Product.code` и `Payment.product` остаются nullable на
весь rollback window: старый writer может создать Payment без product. Поле
`Payment.key` и его nullable OneToOne/SET_NULL контракт не изменяются.
