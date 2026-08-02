# VPN

## Зона ответственности

`apps.vpn` реализует отдельный VPN-продукт: одну подписку на пользователя,
постоянную subscription URL, API покупки и меню, формирование конфигурации HAPP,
а также lifecycle, уведомления и взаимодействие с VPN-нодами. MTProto-модели и
потоки не переиспользуются и не меняются.

## Покупка и бот

Бот получает активный `Product(code="vpn_30d")` для Stars invoice, поэтому
цены и описание управляются через admin. Callback `vpn` запрашивает
`GET /api/v1/vpn/menu/`; `none` и `expired` предлагают только Telegram Stars,
а `active` показывает срок и прежнюю URL. Payload `vpn_stars` направляет
successful payment в `POST /api/v1/vpn/payments/buy/` с `product_code="vpn_30d"`.
Ранее созданный не-XTR invoice продолжает обрабатываться без создания нового
счёта.

Ответ покупки сразу содержит `expired_at` и `subscription_url`. Бот показывает
их с короткой инструкцией HAPP для Android, iOS, Windows и macOS, не ожидая
результата фоновой выдачи профилей.

## Границы MVP

Нет trial, подарков, рефералов, промокодов, автопродления, выбора сервера,
статистики, лимитов устройств/трафика, перевыпуска URL, download-кнопок или
readiness/error state для пользователя. Недоступность VPN-ноды не откатывает
успешный платёж и не скрывает subscription URL.

Для первого production rollout management proxy ноды опубликован по публичному
HTTP без host firewall. Backend продолжает передавать обязательный bearer token,
а proxy допускает только health и profile management routes. Plaintext exposure
является явно принятой временной границей MVP.
