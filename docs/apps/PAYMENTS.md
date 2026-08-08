# Payments

## Зона ответственности

Обработка новых платежей через Telegram Stars и Crypto Pay, а также fulfilment
ранее созданных не-XTR счетов. Фиксирует факт оплаты, определяет стратегию
(продлить существующий ключ или выдать новый), создаёт подарочные сертификаты и
уведомляет пользователя.

## Ключевые модели

- **PaymentMethod** — глобальная доступность поддержанного способа оплаты.
  Django admin меняет только `is_active` существующих `platega_sbp`, `stars` и `crypto_pay`;
  произвольное создание, удаление, label/order и связь с товаром отсутствуют.
- **Product** — товар для Telegram Payments API. Бот использует `stars_price`
  для новых Stars-счетов. Crypto Pay берёт текущий `Product.price` нужного
  товара, а Platega SBP создаёт из него snapshot суммы. Поле хранит целое число
  копеек, которое backend точно делит на 100 и quantize до двух RUB-знаков без
  float. Для подарочного сертификата используется `mtproto_30d`.
- **Payment** — запись об оплате. Связывает пользователя, ключ, charge_id,
  провайдер и тип платежа: `SUBSCRIPTION`, `VPN_SUBSCRIPTION` или
  `GIFT_CERTIFICATE`; это покрывает соответственно MTProto, VPN и подарок.
- **GiftCertificate** — одноразовый код `KEY-XXXX-XXXX` на 30 дней подписки. Покупается отдельно от подписки, действует 1 год до активации, после активации хранит получателя и дату активации.
- **CryptoPaymentIntent** — backend-owned lifecycle счёта Crypto Pay. Один
  активный или создаваемый intent доступен для пары инициатор/вид покупки;
  provider invoice и `Payment` связываются однократно.
- **PlategaPaymentIntent** — отдельный backend-owned lifecycle one-time SBP
  ссылки. `creating|active` ограничены одной парой инициатор/вид покупки;
  provider transaction и `Payment` имеют независимые unique связи. Admin
  доступен только для чтения.

## Доступность способов оплаты

Оба существующих product GET возвращают аддитивные поля `payment_methods` и
`rub_amount`. Последнее — строка с ровно двумя знаками RUB, вычисленная из
целых копеек `Product.price`; прежние `price`, `stars_price` и provider data не
меняются. Selector на каждом запросе читает `PaymentMethod.objects.active()`
без кеша, ограничивает результат поддержанными кодами и сортирует СБП → Stars →
Crypto Pay.
Список глобален для MTProto, VPN и подарочного сертификата; отдельной связи с
`Product` и отдельного config endpoint нет.

Бот получает список вместе с ценой товара. При пустом списке новый экран
показывает `Оплата временно недоступна` и только соответствующую кнопку «Назад».
Нажатие уже показанной старой кнопки не проверяет активность повторно, а цены,
invoice, successful-payment routing и fulfilment действующих Stars/Crypto Pay
сценариев не меняются. Миграция сохраняет существующие Stars/Crypto Pay строки и
создаёт `platega_sbp` неактивным; повторный seed не перезаписывает сохранённое
администратором состояние.

## Сервисы

- **CreatePaymentService** — оркестратор платежа. Ищет пользователя, определяет стратегию (extend/issue), создаёт Payment, отправляет уведомление через SendNotificationService.
- **ExtendKeyService** — продлевает срок действия существующего ключа на SUBSCRIPTION_PERIOD_DAYS.
- **CreateGiftCertificateService** — фиксирует успешную оплату подарочного сертификата и создаёт одноразовый код без продления подписки покупателя. Повторная обработка того же платежа идемпотентно возвращает существующий код.
- **ActivateGiftCertificateService** — активирует валидный сертификат: продлевает активный ключ получателя на 30 дней или выдаёт новый ключ на 30 дней.
- **CreateOrReuseCryptoInvoiceService** — создаёт либо возвращает 30-минутный
  RUB-счёт для USDT/TON без PII в provider payload.
- **CreateOrReusePlategaInvoiceService** — для `subscription` и
  `gift_certificate` выбирает `mtproto_30d`, для `vpn_subscription` —
  `vpn_30d`; сохраняет текущую Decimal RUB-сумму и создаёт либо возвращает
  15-минутную SBP-ссылку. Живой `active` intent возвращается повторно. Локально
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
  только точное совпадение сохранённых transaction ID, Decimal RUB-суммы,
  `currency=RUB` и `payment_method=2`. `CONFIRMED` валиден для
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
- **ReconcileCryptoPaymentsService** — каждые 10 минут повторно сверяет
  незавершённые покупки и восстанавливает доставку результата.

## Зависимости

Зависит от: core (декораторы, исключения), users (поиск пользователя), vds
(выдача/продление ключей), vpn (выдача подписки), notifications (уведомление об
оплате), Crypto Pay HTTP API и Platega create API. От него зависят: бот (Stars,
создание Crypto/Platega-счёта и активация сертификата). Provider credentials
остаются только в Django/Celery environment.
