# VPN

## Зона ответственности

`apps.vpn` реализует отдельный VPN-продукт: одну подписку на пользователя,
постоянную subscription URL, API покупки и меню, формирование конфигурации HAPP,
а также lifecycle, уведомления и взаимодействие с VPN-нодами. MTProto-модели и
потоки не переиспользуются и не меняются.

## Покупка и бот

Бот получает активный `Product(code="vpn_30d")` для каждого invoice, поэтому
цены и описание управляются через admin. Callback `vpn` запрашивает
`GET /api/v1/vpn/menu/`; `none` и `expired` предлагают ЮKassa и Stars, `active`
показывает срок и прежнюю URL. Payload `vpn_yukassa` или `vpn_stars` направляет
successful payment только в `POST /api/v1/vpn/payments/buy/` с
`product_code="vpn_30d"`.

Ответ покупки сразу содержит `expired_at` и `subscription_url`. Бот показывает
их с короткой инструкцией HAPP для Android, iOS, Windows и macOS, не ожидая
результата фоновой выдачи профилей.

## Границы MVP

Нет trial, подарков, рефералов, промокодов, автопродления, выбора сервера,
статистики, лимитов устройств/трафика, перевыпуска URL, download-кнопок или
readiness/error state для пользователя. Недоступность VPN-ноды не откатывает
успешный платёж и не скрывает subscription URL.
