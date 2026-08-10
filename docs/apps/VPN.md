# VPN

## Зона ответственности

`apps.vpn` реализует отдельный VPN-продукт: одну подписку на пользователя,
постоянную subscription URL, API покупки и меню, формирование конфигурации HAPP,
а также lifecycle, уведомления и взаимодействие с VPN-нодами. MTProto-модели и
потоки не переиспользуются и не меняются.

## Покупка и бот

При открытии покупки бот получает активный `Product(code="vpn_30d")` через
существующий product GET, поэтому цены и описание управляются через admin. Тот
же ответ содержит глобальный `payment_methods` без кеша: при двух активных
способах VPN показывает Telegram Stars первым и Crypto Pay вторым, а при пустом
списке — `Оплата временно недоступна` и текущую кнопку «Назад».

Существующие `stars_price`, Stars/Crypto Pay invoice callbacks, payload,
successful-payment routing и fulfilment не меняются. Payload `vpn_stars`
направляет successful payment в `POST /api/v1/vpn/payments/buy/` с
`product_code="vpn_30d"`; ранее созданный не-XTR invoice продолжает
обрабатываться без создания нового счёта.

Ответ покупки сразу содержит `expired_at` и `subscription_url`. Бот показывает
их с короткой инструкцией HAPP для Android, iOS, Windows и macOS, не ожидая
результата фоновой выдачи профилей.

При каждом успешном refresh по действующей subscription URL backend заново
перемешивает блоки активных VPN-нод для более равномерного распределения первого
подключения. Для каждой ноды в ответе по-прежнему идут ровно два соседних
профиля в порядке `VLESS`, затем `Hysteria2`; стабильный per-user порядок не
гарантируется.

## Границы MVP

Нет trial, подарков, рефералов, промокодов, автопродления, выбора сервера,
статистики, лимитов устройств/трафика, перевыпуска URL, download-кнопок или
readiness/error state для пользователя. Недоступность VPN-ноды не откатывает
успешный платёж и не скрывает subscription URL.

Для первого production rollout management proxy ноды опубликован по публичному
HTTP без host firewall. Backend продолжает передавать обязательный bearer token,
а proxy допускает только health и profile management routes. Plaintext exposure
является явно принятой временной границей MVP.
