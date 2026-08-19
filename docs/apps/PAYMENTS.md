# Payments

## Зона ответственности

Обработка новых платежей через one-time Platega SBP, Telegram Stars и Crypto
Pay, а также fulfilment ранее созданных не-XTR счетов. Фиксирует факт оплаты,
определяет стратегию (продлить существующий ключ или выдать новый), создаёт
подарочные сертификаты, начисляет apple cashback за подходящие MTProxy-покупки,
обменивает яблоки на продление существующего ключа и координирует единственного
владельца результата для каждого payment path.

## Ключевые модели

- **PaymentMethod** — глобальные доступность, приоритет и процент комиссии
  поддержанного способа оплаты. Django admin независимо меняет `is_active`,
  `is_priority` и `commission_percent` существующих `platega_sbp`, `stars` и
  `crypto_pay`; одновременно приоритетными могут быть несколько способов.
  Произвольное создание, удаление, label/order и связь с товаром отсутствуют.
- **Product** — товар для Telegram Payments API. Бот использует `stars_price`
  для новых Stars-счетов. Crypto Pay берёт текущий `Product.price` нужного
  товара, а Platega SBP создаёт из него snapshot суммы. Поле хранит целое число
  копеек, которое backend точно делит на 100 и quantize до двух RUB-знаков без
  float. Для подарочного сертификата используется `mtproto_30d`.
- **Payment** — запись об оплате. Связывает пользователя, ключ, charge_id,
  провайдер и тип платежа: `SUBSCRIPTION`, `VPN_SUBSCRIPTION` или
  `GIFT_CERTIFICATE`; это покрывает соответственно MTProto, VPN и подарок.
- **AppleCashbackPurchase** — one-to-one loyalty snapshot подходящего `Payment`
  с unique `identity_key`, применённой ставкой, начислением, balance/count after
  и nullable MTProxy expiry. Historical строки имеют nullable rate, нулевые
  apples/balance и участвуют только в count/level.
- **AppleRedemption** — owner/key-scoped сохранённый quote и подтверждённый
  результат обмена: spend, показанный expiry, nullable committed expiry и
  balance. Model PK является `confirmation_id`.
- **GiftCertificate** — одноразовый код `KEY-XXXX-XXXX` на 30 дней подписки. Покупается отдельно от подписки, действует 1 год до активации, после активации хранит получателя и дату активации.
- **CryptoPaymentIntent** — backend-owned lifecycle счёта Crypto Pay. Один
  активный или создаваемый intent доступен для пары инициатор/вид покупки;
  provider invoice и `Payment` связываются однократно.
- **PlategaPaymentIntent** — отдельный backend-owned lifecycle one-time SBP
  ссылки. `creating|active` ограничены одной парой инициатор/вид покупки;
  provider transaction и `Payment` имеют независимые unique связи. Admin
  доступен только для чтения.

## Доступность способов оплаты

Оба существующих product GET возвращают аддитивные поля `payment_methods`,
`priority_payment_methods` и `rub_amount`. Последнее — строка с ровно двумя
знаками RUB, вычисленная из целых копеек `Product.price`; прежние `price`,
`stars_price` и provider data не меняются. Selector доступности на каждом
запросе читает `PaymentMethod.objects.active()` без кеша, ограничивает результат
поддержанными кодами и сортирует СБП → Stars → Crypto Pay. Отдельный priority
selector дополнительно оставляет только строки с `is_priority=True`, поэтому
неактивный отмеченный способ не попадает в `priority_payment_methods`; список
остаётся упорядоченной подпоследовательностью `payment_methods`.
Список глобален для MTProto, VPN и подарочного сертификата; отдельной связи с
`Product` и отдельного config endpoint нет.

Бот сохраняет оба списка как immutable tuple в snapshot `StarsInvoice` и
передаёт их builder-ам экранов MTProxy, VPN и подарочного сертификата. Наличие и
порядок кнопок по-прежнему определяет только `payment_methods`; доступная кнопка
получает `style="primary"` только при наличии её кода в
`priority_payment_methods`, а остальные доступны без стиля. При пустом списке
доступности экран показывает `Оплата временно недоступна` и только
соответствующую кнопку «Назад»; при пустом priority все доступные кнопки
нейтральны. Все три непустых экрана содержат заголовок оплаты, продукт, период
30 дней и описание результата покупки, после которого идут применимое
юридическое уведомление, одна пустая строка и финальный CTA
`👇 <b>Выберите способ оплаты:</b>`. Stars-label для MTProxy, VPN и подарочного сертификата
берёт сумму из текущего product invoice. Нажатие уже показанной старой кнопки не
проверяет активность или приоритет повторно; empty-state, состав, порядок,
style и callbacks кнопок, а также invoice, successful-payment routing и
fulfilment не меняются. Миграция
сохраняет существующие Stars/Crypto Pay строки и их активность, задаёт всем
способам default priority `False` и commission `0.00%`, а `platega_sbp` —
`8.00%` без изменения сохранённого `is_active`. Отсутствующая строка Platega
создаётся неактивной.

Общий экран счёта Platega СБП для MTProxy, VPN и подарочного сертификата
показывает `Срок действия счета: 15 минут` без технического ISO timestamp.

## Apple cashback

Правила фиксированы в коде. Completed eligible purchase count `0..3`, `4..6`,
`7+` соответствует уровням `Новичок`, `Садовник`, `Мастер сада` и ставкам
5%, 10%, 15%. Для текущей оплаты ставка выбирается до увеличения count, поэтому
покупки 1–4 получают 5%, 5–7 — 10%, 8+ — 15%. `calculate_apples` умножает
номинальную RUB-сумму на ставку и округляет целые яблоки через
`ROUND_HALF_UP`; 1 RUB cashback = 1 яблоко. Sync MTProxy/gift берёт активный
`Product(mtproto_30d).price`, Crypto — `CryptoPaymentIntent.rub_amount`,
Platega — полный `PlategaPaymentIntent.rub_amount`, а не provider amount после
комиссии.

Подходящие `Payment.kind` — только `SUBSCRIPTION` и `GIFT_CERTIFICATE`;
владельцем gift cashback остаётся `Payment.user`. VPN, free/referral grants,
certificate activation и redemption count/balance не увеличивают. Additive
backfill создаёт дедуплицированные historical `AppleCashbackPurchase` по
`(created_at, pk)`, присваивает пустым charge ID `legacy:<payment.pk>` и
оставляет `SystemUser.apple_balance=0`. Такой purchase распознаётся по
`rate_percent IS NULL`: повтор возвращает только
`{"kind":"historical_replay"}`, не выполняет product/payment/loyalty mutation
и не ставит success notification. Post-launch duplicate возвращает сохранённый
полный expiry/code + loyalty outcome.

Subscription/gift fulfilment, purchase snapshot и update `apple_balance`
составляют одну `transaction.atomic()` с user row lock; unique identity остаётся
второй exactly-once границей. Sync Stars/Yukassa result отправляет только bot
handler. Crypto/Platega notification task после commit читает связанный
purchase snapshot, добавляет к прежнему шаблону начисление, ставку, баланс,
уровень и level-up, сохраняет прежний markup и отмечает delivery только после
успешного Telegram transport. Historical row отфильтровывается из enqueue/
reconciliation и безопасно прекращает task до transport.

`GetAppleStatusService` выводит balance/count/level/progress, полные пакеты и
наличие ключа. `PreviewAppleRedemptionService` принимает `one_day|all`, выбирает
сначала лучший active ключ пользователя, иначе лучший датированный existing
key, и сохраняет quote `max(expired_date, preview_at)+days` без debit или key
mutation. Курс `APPLES_PER_DAY=15`; `all` списывает только полные пакеты.
`ConfirmAppleRedemptionService` по owner + `confirmation_id` блокирует quote,
user и выбранный key, отклоняет stale key/balance без mutation, атомарно
списывает apples, сохраняет `max(current_expiry, confirmation_at)+days` и
`user_notified=False`. Повтор завершённого confirmation возвращает stored
outcome без повторного сброса флага. Реактивация expired/cleaned key после commit
ставит существующий `push_key_to_servers_task`; active-key extension не делает
синхронных VDS-вызовов, а first-key issue не вызывается.

Daily one-day notifier отмечает успешную отправку одним conditional update по
ID ключа, точному выбранному `expired_date` и текущему
`user_notified=False`. Поэтому платное продление или подтверждённый обмен яблок,
которые во время отправки сохраняют новый срок и сбрасывают флаг, не
перезаписываются устаревшей отметкой старого срока; при неизменном сроке отметка
обычно устанавливается в `True`.

Bot-facing POST routes `/api/v1/payments/apples/status/`,
`/api/v1/payments/apples/redemptions/preview/` и
`/api/v1/payments/apples/redemptions/confirm/` защищены `Bot-Auth-Token` и
принимают только backend-authoritative identifiers/mode. Eligibility и
validation дают `400`, storage retryable — `503`, повтор подтверждённого
redemption — сохранённый `200`. Бот показывает `🍏 Мои яблоки`, всегда видимое
`🍏 Потратить яблоки`, сохранённый `Продление до: <дата>` и committed balance;
rate, spend и expiry он не вычисляет.

После появления post-launch purchase/redemption state rollback приложения
выполняется только roll-forward с сохранением аддитивного user field и обеих
таблиц: старый SHA не должен принимать новые подходящие оплаты. Нет admin-
настроек, clawback, expiry/transfer/cash яблок, отдельной очереди/cache/service,
общего lock/retry framework или generic loyalty engine. Provider availability,
VPN, referrals/free periods, certificate activation и fleet reconcile
инварианты не меняются.

## Сервисы

- **CreatePaymentService** — атомарно оркестрирует MTProxy-платёж, стратегию
  extend/issue, `Payment`, `AppleCashbackPurchase` и баланс; Telegram success
  сам не отправляет и для повторной identity возвращает сохранённый результат.
- **ExtendKeyService** — продлевает срок действия существующего ключа на
  SUBSCRIPTION_PERIOD_DAYS и вместе с новой датой сохраняет
  `user_notified=False`, возвращая ключ в цикл one-day reminder.
- **CreateGiftCertificateService** — атомарно фиксирует оплату, создаёт
  одноразовый код и buyer-owned cashback без продления подписки покупателя;
  повторная обработка возвращает сохранённые code и loyalty.
- **ActivateGiftCertificateService** — активирует валидный сертификат: продлевает активный ключ получателя на 30 дней или выдаёт новый ключ на 30 дней.
- **GetAppleStatusService**, **PreviewAppleRedemptionService** и
  **ConfirmAppleRedemptionService** — backend-authoritative status, immutable
  quote и атомарный idempotent debit/extension существующего MTProxy-ключа.
- **CreateOrReuseCryptoInvoiceService** — создаёт либо возвращает 30-минутный
  RUB-счёт для USDT/TON без PII в provider payload.
- **CreateOrReusePlategaInvoiceService** — для `subscription` и
  `gift_certificate` выбирает `mtproto_30d`, для `vpn_subscription` —
  `vpn_30d`; сохраняет полную пользовательскую Decimal RUB-сумму, а для нового
  intent читает текущий глобальный процент `platega_sbp` и передаёт provider
  amount `user_amount / (1 + commission_percent / 100)`, один раз округлённую
  до `0.01` с `ROUND_HALF_UP`. При `99.00` и `8.00%` Platega получает numeric
  `91.67`, тогда как intent/API/bot сохраняют `99.00`; при `0.00%` provider
  получает `99.00`. Отсутствующая строка настройки даёт безопасный
  `payment_method_unavailable` 503 без provider POST. Сервис создаёт либо
  возвращает 15-минутную SBP-ссылку. Живой `active` intent возвращается
  повторно без перечитывания ставки. Локально
  истёкший `active` становится `local_expired`, зависший дольше двух provider
  timeout `creating` — `create_failed`, а `provider_canceled` и
  `create_failed` разрешают новую ссылку. Текущие `creating`, `processing` и
  `retryable` безопасно блокируют новое создание. Резервирование
  `creating`/выбор winner выполняется в короткой DB-транзакции; provider POST
  выполняется после неё и переводит только свой `creating` в `active` либо
  `create_failed` с allowlisted reason code.
- **ValidateCryptoInvoiceService** и **ApplyCryptoPaymentService** — проверяют
  signed invoice и условно выполняют выдачу ровно один раз.
- **ValidatePlategaCallbackService** — после HTTP-аутентификации находит intent
  по provider transaction UUID с загруженными initiator/payment и принимает
  совпавшие transaction ID, `currency=RUB`, `payment_method=2` и Decimal amount
  не меньше сохранённой пользовательской `rub_amount`. Amount сравнивается без
  округления: равенство и любая переплата проходят, недоплата остаётся mismatch.
  `CONFIRMED` валиден для
  `active|local_expired|retryable|processing|fulfilled`; применение duplicate и
  concurrent состояний остаётся обязанностью apply-сервиса. Совпавший
  `CANCELED` переводит только `active|local_expired` в `provider_canceled`.
  Unknown transaction, mismatch и unsupported status, включая
  `CHARGEBACKED`, возвращают обязательный warning только из `reason_code`,
  nullable internal intent ID и nullable provider transaction UUID. Обычная или
  повторная отмена warning не создаёт. Эти safe-ack исходы не меняют продукт и
  не выполняют Platega GET/status polling.
- **ApplyPlategaPaymentService** — условно захватывает подтверждённый
  `active|local_expired|retryable` intent в `processing` и в одной атомарной
  операции вызывает ровно одну существующую MTProto, VPN или gift fulfilment
  границу с `provider=platega` и UUID transaction как `charge_id`, связывает
  созданный `Payment` и завершает intent. Поэтому поздний `CONFIRMED` старого
  `local_expired` intent обрабатывается независимо и не меняет более новый
  `active` intent. Ошибка откатывает продукт и Payment, а intent становится
  `retryable`; duplicate/concurrent вызов не повторяет выдачу. После успешной
  фиксации сервис условно ставит `notification_queued_at` и только через
  `transaction.on_commit` вызывает инъецированный publisher. Для fulfilled
  intent с пустым marker повторяется только публикация. Ошибка publisher-а
  очищает лишь захваченный marker и возвращает безопасную retryable ошибку;
  непустой marker исключает вторую постановку.
- **notify_platega_purchase_task** — bound Celery-задача с максимум тремя
  retry. Selector допускает только `fulfilled` intent с непустым
  `notification_queued_at` и пустым `notification_sent_at`, заранее загружая
  initiator, Payment и связи сохранённого результата. MTProto получает
  сохранённую дату исходного результата через `proxy_purchased`, VPN — дату и постоянный
  subscription URL через `crypto_vpn_purchased`, подарок — сохранённый code
  через `crypto_gift_certificate_purchased`. Для MTProxy/gift добавляется
  сохранённый loyalty-блок; historical row не доставляется. Sent marker ставится условно
  только после успешного Telegram transport; ошибка сохраняет unsent и
  повторяется с безопасным exception context. Все slugs уже существуют,
  поэтому notifications migration не добавляется.
- **ReconcileCryptoPaymentsService** — каждые 10 минут повторно сверяет
  незавершённые покупки и восстанавливает доставку результата.

## Platega callback boundary

Публичный `POST /api/v1/payments/platega/callback/` имеет пустые DRF
authentication/permission lists. До request data/body parsing он выполняет обе
отдельные constant-time проверки raw `X-MerchantId` и `X-Secret`; пустые
configured credentials и missing/invalid headers дают `401`. Только
authenticated payload с пятью обязательными provider-полями и необязательным
игнорируемым echo `payload` преобразуется в `PlategaCallbackDTO` и передаётся
validator/apply factories. Callback-only JSON parser разбирает
integer, fraction и finite exponent tokens напрямую в Decimal. Amount принимает
только конечное JSON-число произвольной точности; numeric strings, boolean,
`null`, containers, `NaN` и бесконечности отклоняются без domain processing.

Malformed, unknown, mismatch, unsupported (включая `CHARGEBACKED`), canceled и
duplicate исходы дают empty `200`; successful fulfilled+queued также даёт
`200`. DB/fulfilment/publish failure и concurrent processing дают empty `503`.
Mandatory warning для unknown/mismatch/unsupported содержит ровно
`reason_code`, nullable internal intent ID и nullable provider transaction ID;
ни request, body/headers, settings/credentials, user, provider content, metadata,
payload или payment URL не логируются. Callback использует только сохранённые
данные и никогда не вызывает provider GET/status polling.

## Зависимости

Зависит от: core (декораторы, исключения), users (`SystemUser`, поиск и
блокировка пользователя, `apple_balance`), vds (выдача/продление/реактивация
ключей и async push), vpn (выдача подписки), notifications (шаблоны результата
оплаты), Crypto Pay HTTP API и Platega create API. От него зависят: бот (Stars,
создание Crypto/Platega-счёта, apple status/redemption и активация
сертификата). Provider credentials остаются только в Django/Celery environment;
бот не получает key token, provider secret или авторитетные loyalty inputs.
