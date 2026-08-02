# Payments

## Зона ответственности

Обработка новых платежей через Telegram Stars и Crypto Pay, а также fulfilment
ранее созданных не-XTR счетов. Фиксирует факт оплаты, определяет стратегию
(продлить существующий ключ или выдать новый), создаёт подарочные сертификаты и
уведомляет пользователя.

## Ключевые модели

- **Product** — товар для Telegram Payments API. Бот использует `stars_price`
  для новых Stars-счетов. Crypto Pay берёт текущий `Product.price` нужного
  товара: существующее поле хранит целое число копеек, которое backend точно
  делит на 100 и quantize до двух RUB-знаков без float. Для подарочного
  сертификата используется `mtproto_30d`.
- **Payment** — запись об оплате. Связывает пользователя, ключ, charge_id,
  провайдер и тип платежа: `SUBSCRIPTION`, `VPN_SUBSCRIPTION` или
  `GIFT_CERTIFICATE`; это покрывает соответственно MTProto, VPN и подарок.
- **GiftCertificate** — одноразовый код `KEY-XXXX-XXXX` на 30 дней подписки. Покупается отдельно от подписки, действует 1 год до активации, после активации хранит получателя и дату активации.
- **CryptoPaymentIntent** — backend-owned lifecycle счёта Crypto Pay. Один
  активный или создаваемый intent доступен для пары инициатор/вид покупки;
  provider invoice и `Payment` связываются однократно.

## Сервисы

- **CreatePaymentService** — оркестратор платежа. Ищет пользователя, определяет стратегию (extend/issue), создаёт Payment, отправляет уведомление через SendNotificationService.
- **ExtendKeyService** — продлевает срок действия существующего ключа на SUBSCRIPTION_PERIOD_DAYS.
- **CreateGiftCertificateService** — фиксирует успешную оплату подарочного сертификата и создаёт одноразовый код без продления подписки покупателя. Повторная обработка того же платежа идемпотентно возвращает существующий код.
- **ActivateGiftCertificateService** — активирует валидный сертификат: продлевает активный ключ получателя на 30 дней или выдаёт новый ключ на 30 дней.
- **CreateOrReuseCryptoInvoiceService** — создаёт либо возвращает 30-минутный
  RUB-счёт для USDT/TON без PII в provider payload.
- **ValidateCryptoInvoiceService** и **ApplyCryptoPaymentService** — проверяют
  signed invoice и условно выполняют выдачу ровно один раз.
- **ReconcileCryptoPaymentsService** — каждые 10 минут повторно сверяет
  незавершённые покупки и восстанавливает доставку результата.

## Зависимости

Зависит от: core (декораторы, исключения), users (поиск пользователя), vds
(выдача/продление ключей), vpn (выдача подписки), notifications (уведомление об
оплате) и Crypto Pay HTTP API. От него зависят: бот (Stars, создание
Crypto-счёта и активация сертификата). Crypto Pay token и webhook secret остаются
только в Django/Celery environment.
