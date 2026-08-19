# Payments

## Зона ответственности

Каталог товаров и способов оплаты, payment intents, fulfilment MTProxy/VPN/gift,
подарочные сертификаты и apple cashback/redemption. Пользовательские правила
принадлежат [BUSINESS.md](../BUSINESS.md), HTTP/provider контракты —
[CONTRACTS.md](../CONTRACTS.md), хранение — [MODELS.md](../MODELS.md), границы
транзакций и фоновой доставки — [ARCHITECTURE.md](../ARCHITECTURE.md).

## Карта компонентов

- Product, PaymentMethod, Payment — каталог, доступность и результат оплаты.
- CryptoPaymentIntent, PlategaPaymentIntent — provider lifecycle и idempotency.
- GiftCertificate — покупка и активация подарка.
- AppleCashbackPurchase, AppleRedemption — loyalty snapshots и redemption quote.
- create/apply payment services — синхронный и callback fulfilment.
- apple redemption services — status, preview и confirm.
- provider clients/validators — внешние invoice и callback boundaries.
- notification/reconciliation tasks — post-commit доставка и восстановление.
- api/v1 — bot-authenticated routes и публичные provider callbacks.

## Зависимости

Использует users, VDS, VPN, notifications, core и внешние Crypto Pay/Platega
API. Бот вызывает только backend API и не получает provider credentials или
авторитетные cashback inputs.

## Границы

Payments владеет exactly-once обработкой оплаты и loyalty, но не Telegram
навигацией, MTProxy fleet state или VPN node delivery. Provider secrets остаются
только в Django/Celery environment.
