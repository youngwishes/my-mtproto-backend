# VPN

## Зона ответственности

`apps.vpn` реализует отдельный VPN-продукт: одну подписку на пользователя,
subscription URL, API покупки, меню и перевыпуска, формирование конфигурации
HAPP, а также lifecycle, уведомления и взаимодействие с VPN-нодами.
MTProto-модели и потоки не переиспользуются и не меняются.

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

Default `VPN_SUBSCRIPTION_BASE_URL` равен `https://dash.mtprotokeys.com`;
существующий builder сохраняет subscription path и token без изменений.

Экран `🔑 Моя подписка` показывает `🔄 Перевыпустить ссылку` для active и
expired-подписки. Нажатие для expired/inactive сразу выводит сообщение о том,
что перевыпуск доступен только после продления, без подтверждения, mutation или
backend-вызова. Для active-подписки бот показывает подтверждение; cancel снова
загружает экран без mutation. Success вызывает защищённый
`POST /api/v1/vpn/reissue/`, после чего бот повторно читает menu и показывает
banner с новой subscription URL.

Backend перевыпускает только active-подписку: в одной DB-транзакции он заменяет
subscription token, VLESS UUID и Hysteria secret, сохраняет `expired_at` и
`is_active` и записывает nullable `last_reissued_at`. Cooldown — пять минут и
имеет тот же уровень защиты, что и MTProxy: distributed lock или более сильная
защита от гонок не добавляются. Старая URL сразу возвращает `404`. После commit
ровно один существующий `ScheduleProfilesService` асинхронно ставит idempotent
profile PUT delivery на активные ноды; бот не ждёт node completion и не имеет
readiness/error state. Старые импортированные профили перестают подключаться
eventually после доставки новых credentials.

Перевыпуск не меняет expiry, active-state, payment, renewal или lifecycle flow;
продление и повторная покупка не меняют credentials. Application rollback не
восстанавливает уже заменённые credentials: rotation необратима операционно, а
асинхронная доставка актуального DB state должна завершиться.

При каждом успешном refresh по действующей subscription URL backend заново
перемешивает блоки активных VPN-нод для более равномерного распределения первого
подключения. Для каждой ноды в ответе по-прежнему идут ровно два соседних
профиля в порядке `VLESS`, затем `Hysteria2`; стабильный per-user порядок не
гарантируется.

## Границы MVP

Нет trial, подарков, рефералов, промокодов, автопродления, выбора сервера,
статистики, лимитов устройств/трафика, download-кнопок или readiness/error state
для пользователя. Нет изменения node-agent API, retry/reconcile/bootstrap и нет
синхронного ожидания нод либо более строгой блокировки перевыпуска. Недоступность
VPN-ноды не откатывает успешный платёж и не скрывает subscription URL.

Для первого production rollout management proxy ноды опубликован по публичному
HTTP без host firewall. Backend продолжает передавать обязательный bearer token,
а proxy допускает только health и profile management routes. Plaintext exposure
является явно принятой временной границей MVP.
