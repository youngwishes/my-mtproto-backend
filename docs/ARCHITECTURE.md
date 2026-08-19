# Архитектура

## Место в системе

Этот репозиторий — **центральное звено** платформы. Содержит бизнес-логику, управление пользователями, платежи и реферальную программу. Telegram-бот живёт в поддиректории `bot/`.

```
Пользователь
    │
    ▼
Telegram Bot ─── (bot/)
    │
    ▼
Django Backend ── (src/)               ◄── Celery Beat (расписание)
    │                                       │
    ▼                                       ▼
VDS Instance #1 ── (my-mtproto-vds-instance)
VDS Instance #2
VDS Instance #N
    │
    ▼
telemt (MTProto-прокси)
```

**Telegram Bot** (`bot/`) — Aiogram 3.x, polling-режим. Принимает команды от пользователя, обрабатывает платежи. Общается с бэкендом через REST API с заголовком `Bot-Auth-Token`.

**Django Backend** (`src/`) — Django 6 + DRF. Бизнес-логика, управление ключами, платежи, рефералы. БД — SQLite. Фоновые задачи через Celery + Redis.

**VDS Instance** — FastAPI-сервис на каждом VDS-сервере. Принимает команды от Django и управляет прокси-сервером telemt.

`RequestLoggingMiddleware` для mutating API-запросов сохраняет только HTTP
method и безопасный path. Headers и body не логируются; секреты в URL Crypto
webhook маскируются, а публичный Platega callback полностью обходит middleware
logging до чтения body.

## Стек

| Компонент | Технология |
|-----------|------------|
| Backend | Django 6.0.2, DRF 3.16.1, Python 3.13 |
| Bot | Aiogram 3.x (polling) |
| Очередь задач | Celery 5.6.2 + Redis 7 |
| Мониторинг Celery | Flower |
| Reverse proxy | Nginx (SSL termination) |
| БД | SQLite |
| Пакетный менеджер | uv |
| Деплой | Docker Compose |

## Публичные домены и release gate

Nginx принимает HTTP для ровно `dash.mtprotokeys.com`,
`flower.mtprotokeys.com` и переходного alias `beatvault.ru`: ACME challenge
сохраняется, остальные запросы перенаправляются на HTTPS того же host. На HTTPS
один vhost Django обслуживает `dash.mtprotokeys.com` и `beatvault.ru`, а
отдельный vhost Flower обслуживает только `flower.mtprotokeys.com` с прежней
Compose Basic Auth. Django разрешает только эти два публичных Django-host вместе
с local/container hosts; Flower не направляется в Django.

Переходный сертификат использует существующий lineage
`/etc/nginx/ssl/live/beatvault.ru/` и перед deploy обязан иметь точный SAN-набор:
`beatvault.ru`, `dash.mtprotokeys.com`, `flower.mtprotokeys.com`. Новые
MTProto-секреты используют `TLS_DOMAIN=mtprotokeys.com`, а новые VPN
subscription URL используют `VPN_SUBSCRIPTION_BASE_URL=https://dash.mtprotokeys.com`.
Внутренний Ansible healthcheck посылает `Host: dash.mtprotokeys.com`, но не
заменяет внешнюю проверку валидной TLS chain и SAN.

При неуспешном deploy playbook сохраняет автоматический возврат предыдущего
SHA/Compose stack. Для полного операционного rollback вернуть VPN base и
provider callbacks на `beatvault.ru`, не откатывать `TLS_DOMAIN=mtprotokeys.com`
и не восстанавливать `flower.beatvault.ru` либо `www.beatvault.ru`.

## Компоненты репозитория

- `src/config/` — настройки Django, маршрутизация, Celery и WSGI entrypoint.
- `src/apps/` — доменные и инфраструктурные Django-приложения. Их зоны
  ответственности перечислены в [docs/apps/](apps/).
- `bot/` — отдельное Aiogram-приложение со своим dependency graph и тестами;
  актуальная структура и команды находятся в [bot/README.md](../bot/README.md).
- `integration_tests/` — end-to-end сценарии bot → backend → VDS; требования к
  окружению описаны в
  [integration_tests/README.md](../integration_tests/README.md).
- `ansible/`, Compose- и Nginx-конфигурация — инфраструктура локального запуска и
  production release. Канонический процесс выпуска описан в
  [DEPLOY.md](DEPLOY.md).

Документ фиксирует границы и взаимодействия компонентов, но намеренно не
дублирует дерево файлов: актуальный состав модулей определяется репозиторием и
профильной документацией приложений.

## apps/core — Инфраструктурное ядро

`apps.core` содержит базовые модели, доменные и инфраструктурные исключения,
декораторы обработки ошибок и Telegram-транспорт. Публичные обязанности и
зависимости приложения перечислены в [apps/CORE.md](apps/CORE.md).

## apps/infrastructure — Учёт проектных серверов

`apps.infrastructure` изолированно владеет вручную поддерживаемым через Django
Admin реестром `ProjectServer` и ежедневным напоминанием об оплате. Приложение
зависит от `apps.core` только для базовой модели и Telegram-транспорта, а от
`apps.vds` — только для справочника `Hosting`. VDS/VPN-приложения не зависят от
него; синхронизации с `VDSInstance` или `VPNInstance` нет.

В 11:00 UTC Celery Beat запускает read-only поток:

`Beat → task → factory → selector → ProjectServer + Hosting → service → Telegram → MY_TELEGRAM_ID`.

Selector детерминированно выбирает активные записи с датой платежа не позднее
завтра. Сервис формирует одно HTML-safe сообщение либо ничего не отправляет при
пустой выборке. Bound task повторяет весь read/format/send-вызов до трёх раз с
задержкой 30 секунд; записи, включая просроченные даты и active-state, не
изменяются. Подробности границы находятся в
[apps/INFRASTRUCTURE.md](apps/INFRASTRUCTURE.md).

## Service Layer

Сервисы — frozen dataclasses с `__call__`. Два декоратора (из `apps.core.decorators`):

- `@log_service_error` — бизнес-ошибка → Telegram-уведомление пользователю
- `@log_infra_error` — инфра-ошибка → «извините» пользователю + алерт админу

Исключения (из `apps.core.exceptions`): `BaseServiceError`, `BaseInfraError`.

Каждый файл сервиса определяет фабричную функцию:

```python
def get_first_free_link_service() -> FirstFreeLinkService:
    return FirstFreeLinkService()
```

## Apple cashback

Apple cashback остаётся частью `apps.payments`, а не отдельным loyalty-
приложением. Текущее mutable-состояние — `SystemUser.apple_balance`; уровень и
ставка вычисляются из числа строк `AppleCashbackPurchase`. Эта таблица хранит
уникальную provider identity и неизменяемый результат подходящей оплаты,
`AppleRedemption` — предпросмотр и зафиксированный результат обмена. Других
account/counter/config-таблиц нет: правила `0..3/4..6/7+`, ставки `5/10/15%` и
курс `15 🍏 = 1 день` заданы кодом.

Успешная MTProxy-подписка и покупка подарочного сертификата выполняются вместе
с записью покупки и обновлением баланса внутри обычной DB-транзакции с
блокировкой строки пользователя. Ставка берётся по count до текущей оплаты, а
начисление рассчитывается от номинальной RUB-цены с `ROUND_HALF_UP`. Для
Stars/Yukassa цена читается из активного `Product(mtproto_30d)`, для Crypto и
Platega — из сохранённого полного `intent.rub_amount`; provider currency,
фактическая сумма и комиссия не являются входом расчёта. Уникальный
`AppleCashbackPurchase.identity_key` и существующие provider state machines
дают ровно один product/payment/count/balance effect. VPN, certificate
activation, бесплатные и реферальные выдачи обходят эту границу.

Data migration создаёт для pre-launch `Payment.kind=subscription|gift_certificate`
исторические строки с `rate_percent=NULL`, нулевыми apples/balance snapshot и
порядковым count-after; непустые `(provider, charge_id, kind)` дедуплицируются,
а пустая legacy identity получает `legacy:<payment.pk>`. `Payment.user`
остаётся владельцем подарочной покупки. Поэтому история задаёт уровень, но
`apple_balance` после запуска равен нулю. Повтор такой identity возвращает
только успешный tag `{"kind":"historical_replay"}` и не меняет ключ,
сертификат, Payment, count или баланс.

Владение сообщением разделено по payment path. Для синхронных Stars/Yukassa
только bot handler показывает объединённый expiry/code и loyalty outcome;
`CreatePaymentService` и `CreateGiftCertificateService` Telegram-сообщение не
отправляют. Для Crypto/Platega единственный success sender — существующая
post-commit Celery-задача: она читает сохранённый purchase snapshot, добавляет
loyalty-блок к прежнему шаблону, сохраняет markup и ставит sent marker только
после transport success. Исторический replay не ставит notification и при
прямом вызове task завершается до Telegram transport; reconciliation его не
переочередит. Обычный post-launch duplicate возвращает прежний сохранённый
полный результат без повторных доменных эффектов.

Redemption selector выбирает только ключ пользователя: сначала действующий
active/non-deleted с максимальным `(expired_date, pk)`, иначе существующий
датированный ключ с максимальным `(expired_date, pk)`, включая истёкший или
очищенный. Preview `one_day|all` создаёт pending `AppleRedemption`, сохраняет
spend и `max(expired_date, preview_at)+days`, но не резервирует яблоки и не
меняет ключ. Confirm принимает только owner и `confirmation_id`, блокирует
redemption, пользователя и выбранный ключ и требует, чтобы текущий selector
по-прежнему выбрал тот же key, а balance покрывал сохранённый spend. Рост
баланса не меняет quoted `apples_spent`/days; сдвиг expiry того же ключа также
допустим. Confirm атомарно списывает ровно quote и заново вычисляет committed
дату как `max(current_same_key_expiry, confirmation_at)+days`, поэтому она может
отличаться от показанной preview-даты. Другой выбранный key, удалённый или
недоступный quoted key либо balance ниже quoted spend делают quote stale.
Повтор confirmation возвращает сохранённый outcome. Реактивированный ключ после commit передаётся существующей
`push_key_to_servers_task`; active-key extension остаётся DB-only и обычный
fleet reconciliation доставляет состояние. Issue service и синхронный VDS
вызов в redemption отсутствуют.

Bot использует три защищённых `Bot-Auth-Token` POST-контракта под
`/api/v1/payments/apples/`: status, redemption preview и confirm. Backend один
вычисляет balance/count/level/rate/spend/days/expiry; bot хранит frozen DTO,
показывает `🍏 Мои яблоки`, сохранённый preview и отправляет на confirm только
ID. Eligibility/validation возвращают `400`, временная storage-ошибка — `503`,
повтор успешного confirm — тот же `200`.

Миграции аддитивно добавляют поле пользователя и две payment-owned таблицы.
До первого post-launch credit/redemption возможен rollback application и
schema; после появления нового loyalty state используется roll-forward:
аддитивные schema/data сохраняются, а старый SHA не должен принимать новые
подходящие оплаты. Решение не добавляет очередь, cache, внешний сервис,
distributed lock, общий retry/concurrency framework, event sourcing, admin-
настройку правил или generic loyalty engine и не меняет provider/fleet
инварианты. API и логи не раскрывают Bot auth, provider credentials, key token,
proxy URL или provider body.

## Crypto Pay

Django владеет созданием Crypto Pay-счёта и webhook; bot получает только
четырёхпольный ответ защищённого `Bot-Auth-Token` API и не получает token или
webhook secret. Локальный `CryptoPaymentIntent` хранит состояние покупки,
публичный UUID payload и provider invoice. Вызов провайдера выполняется вне
долгой SQLite-транзакции, а выдача использует conditional transitions и
частичные unique constraints, поэтому повторный webhook или reconciliation не
выдают продукт повторно. После commit отдельная Celery-задача доставляет
результат пользователю.

Webhook проверяет и secret path, и HMAC от raw body. До выдачи сверяются счёт,
RUB-сумма, валюта, paid status и разрешённый/оплаченный asset; безопасные
идентификаторы и reason code достаточны для warning. Token, signature, raw body,
PII и URL результата в логи не попадают. Celery Beat запускает reconciliation
`*/10`, чтобы повторно обработать оплаченные незавершённые покупки и отдельно
доставить пропущенные уведомления.

## Platega SBP

Platega используется только из Django/Celery как отдельный one-time SBP
provider boundary; bot не получает merchant ID или secret. `PlategaClient`
выполняет только `POST {PLATEGA_BASE_URL}/transaction/process`: отправляет
method `2`, `RUB` decimal amount с двумя знаками без float, оба redirect URL из
`BOT_LINK`, случайный local UUID payload и antifraud metadata с Telegram ID и
username (либо Telegram ID как fallback). Для нового intent сервис через
selector читает текущий глобальный `commission_percent` и вычисляет provider
amount как `user_amount / (1 + commission_percent / 100)`, один раз округляя
результат до `0.01` с `ROUND_HALF_UP`; `99.00` при `8.00%` даёт numeric `91.67`.
Intent, invoice API и bot сохраняют пользовательский snapshot `99.00`, а не
provider amount. Живой intent переиспользуется без повторного чтения ставки.
Отсутствующая строка настройки даёт безопасный
`payment_method_unavailable` и существующий ответ `503` до provider POST.

Успешным считается только HTTP `200` с UUID transaction ID, `PENDING` и usable
HTTPS redirect. Provider-controlled echoes, включая `expiresIn`, `return`,
`paymentMethod`, `merchantId` и `paymentDetails`, не используются для
валидации; локальный intent получает фиксированный TTL 15 минут. Ошибки provider
client наружу несут только reason code `timeout`, `unavailable`, `malformed` или
`create_mismatch`; request/response body, URL, metadata и credentials не
логируются. HTTP GET, polling и bot credentials для Platega отсутствуют.

Публичный `POST /api/v1/payments/platega/callback/` не использует Bot auth.
До чтения body/request data Django извлекает raw `X-MerchantId` и `X-Secret` и
всегда вычисляет две отдельные constant-time проверки; пустая backend
конфигурация fail-closed. Только после этого exact-key serializer принимает
обязательные `id`, `amount`, `currency`, `status`, `paymentMethod` и игнорирует
необязательный provider echo `payload`, а validation service сопоставляет
normalized DTO с сохранённым intent. Callback-only JSON parser
разбирает integer, fraction и exponent tokens сразу в Decimal без binary float;
serializer принимает только конечное JSON-число произвольной точности и
отклоняет строки, boolean, `NaN` и бесконечности. Validator без округления
отклоняет только `amount < intent.rub_amount`; равенство и любая переплата
проходят при сохранении остальных exact-проверок. Callback не вызывает Platega
client и не делает status GET.

Совпавший `CONFIRMED` проходит через атомарный fulfilment существующей MTProto,
VPN или gift границы. После commit отдельная bound Celery-задача читает только
сохранённый результат, повторяет Telegram delivery не более трёх раз и
условно ставит `notification_sent_at`. Она переиспользует шаблоны
`proxy_purchased`, `crypto_vpn_purchased` и
`crypto_gift_certificate_purchased`; новой notifications migration нет.
Unknown/mismatch/unsupported callback логирует только allowlist
`reason_code`, nullable internal intent ID и nullable provider transaction ID.
В штатном режиме credentials, headers/body, Telegram identity, metadata,
payload, provider content и payment URL не передаются logger-у. Временный
`PLATEGA_CALLBACK_DEBUG_LOGGING=true` после успешной аутентификации добавляет
один диагностический INFO с raw body, method/path, Content-Type/User-Agent и
названиями заголовков; значения merchant/secret, Authorization и Cookie в него
не входят. `CHARGEBACKED` остаётся только unsupported safe acknowledgement без
доменного перехода.

## Доступность способов оплаты

`PaymentMethod` в `apps.payments` хранит глобальные `is_active`, `is_priority` и
`commission_percent` для каждого поддержанного кодом способа (`platega_sbp`,
`stars`, `crypto_pay`). Процент — non-null Decimal `0.00..999.99` с model- и
DB-ограничением; `is_priority` — независимо редактируемый boolean с default
`False`, который можно одновременно включить у нескольких способов. Настройки
относятся к способу, а не к товару. Модель не связана с `Product`: Django admin
меняет `commission_percent`, `is_active` и `is_priority` глобально для MTProto,
VPN и подарочного сертификата; добавление, удаление и переименование способов
отключены.

При каждом `GET /api/v1/payments/` или
`GET /api/v1/payments/products/<code>/` selectors читают строки из БД без кеша,
отбрасывают неизвестные коды и возвращают `payment_methods` в фиксированном
порядке СБП → Stars → Crypto Pay, а `priority_payment_methods` — как его
упорядоченную подпоследовательность активных строк с `is_priority=True`.
Неактивный отмеченный способ не попадает ни в один список. Бот сохраняет оба
списка в `StarsInvoice`: наличие и порядок кнопок определяет только
`payment_methods`, а `priority_payment_methods` задаёт `style="primary"` только
отмеченным кнопкам на экранах MTProxy, VPN и подарочного сертификата. Остальные
доступные кнопки и все кнопки при пустом priority нейтральны. Пустой список
доступности — штатное состояние: экран содержит `Оплата временно недоступна` и
текущую кнопку «Назад». Приоритет не меняет цены, callback-данные или payment
flow; ошибки product API не маскируются под empty-state, а обработчики уже
показанных платёжных кнопок не перечитывают активность или приоритет.

Commission migration даёт остальным способам `0.00%`, устанавливает
`platega_sbp` ставку `8.00%` и не изменяет ни один сохранённый `is_active`;
отсутствующая строка создаётся выключенной. Поэтому перед whole-stack deploy
операционный gate обязан подтвердить, что `platega_sbp` выключен. После deploy
проверяются migration state, ставка и сохранённые переключатели, а включение
остаётся отдельным последующим gate. Перед rollback способ снова выключается и
остаётся выключенным на старом SHA; additive column/data и реальные платежи не
удаляются.

Отдельная additive migration добавляет `is_priority` с default `False`, не
изменяя сохранённые доступность, комиссию и платёжные данные.

### Ежедневная выдача бесплатных периодов

Celery Beat в 12:00 UTC вызывает тонкую задачу
`apps.users.tasks.grant_daily_free_trials_task`. Selector в `apps.users` выбирает
не активировавших пробный период пользователей по `date_joined, pk` (`date_joined`
является timestamp создания у `SystemUser`, наследуемым от `AbstractUser`).
`DailyFreeTrialGrantService` получает selector, сервис выдачи, selectors ключа и
активных VDS и Telegram transport через DI. Он продолжает обход после ошибки до
десяти сохранённых активаций, после чего отправляет один итоговый отчёт админу.

`FirstFreeLinkService` блокирует строку пользователя через `select_for_update()`
и повторно проверяет `first_month_free_used` внутри транзакции. Поэтому
параллельный или повторный запуск не может выдать одному пользователю два
бесплатных периода. Выдача остаётся DB-only; доставка секрета на healthy VDS
выполняется существующей reconcile-задачей.

## apps/notifications — Уведомления и рассылки

`apps.notifications` хранит шаблоны сообщений и рассылок, выбирает получателей,
разрешает контекст и ставит отправку в Celery. Обзор моделей, сервисов и
зависимостей находится в [apps/NOTIFICATIONS.md](apps/NOTIFICATIONS.md).

`NotificationTemplate` хранит HTML-текст с `{переменными}`, опциональную кнопку и флаг `include_payment_buttons` (добавляет кнопку «⚡Продлить» с `callback_data="boost_paid"`). Кнопка может быть URL (`button_url`) или callback (`button_callback_data`) — URL имеет приоритет.

`Mailing` отслеживает статусы: DRAFT → SENDING → COMPLETED / PARTIALLY_COMPLETED / FAILED. Поля `sent_count` и `failed_count` фиксируют результаты рассылки.

## Аутентификация

Все API-эндпоинты защищены заголовком `Bot-Auth-Token`, проверяемым через permission `BotAuthToken` против `settings.BOT_AUTH_TOKEN`.

## VPN

`apps.vpn` хранит единственную VPN-подписку пользователя с subscription token,
VLESS UUID, Hysteria secret и nullable `last_reissued_at`. Бот запрашивает
read-only menu endpoint, получает цены только из активного
`Product(code="vpn_30d")`, а successful payment направляет исключительно в
`/api/v1/vpn/payments/buy/`. Ответ покупки содержит срок и внешнюю
subscription URL; бот показывает её сразу и не ждёт фоновой выдачи профилей на
VPN-ноды. Продление и платёжный flow не меняются credentials.

`POST /api/v1/vpn/reissue/` защищён `BotAuthToken` и принимает только
`username`. Для active-подписки `ReissueVPNSubscriptionService` без более
строгой блокировки, чем у MTProxy, проверяет пятиминутный cooldown, в одной
транзакции заменяет token, VLESS UUID и Hysteria secret и записывает
`last_reissued_at`; `expired_at` и `is_active` сохраняются. Неактивная или
истёкшая подписка не изменяется: бот отказывает ей локально до вызова endpoint,
а backend также отклоняет её при прямом запросе. После commit service ровно один
раз вызывает существующий `ScheduleProfilesService`, который ставит текущие
idempotent profile PUT-задачи для активных VPN-нод. Это не readiness-протокол:
старый URL сразу возвращает `404`, а прежние профили перестают работать
eventually, когда асинхронная доставка заменит credentials на нодах.

В боте обе subscription-клавиатуры содержат `vpn_reissue`. Active-подписка
показывает подтверждение, cancel возвращает к повторно загруженному экрану без
mutation, а success вызывает backend, повторно читает menu и добавляет banner с
новой URL. Cooldown backend остаётся в существующем error path. Node-agent,
delivery retries, MTProxy и payment/lifecycle flows не меняются.

Откат application SHA не возвращает уже ротированные token или credentials:
rotation необратима для операционного rollback, а существующая асинхронная
доставка актуального DB state должна завершиться.

VPN callbacks и invoice payload отделены от MTProto: `vpn`,
`vpn_pay_yukassa`/`vpn_pay_stars` и `vpn_yukassa`/`vpn_stars`. Статусы меню
`none`, `active`, `expired` формирует backend; бот ветвится только по этому
полю. Уведомления VPN ведут в callback `vpn`.

## Деплой

Docker Compose с 8 сервисами:

| Сервис | Назначение | Порт |
|--------|------------|------|
| django | Django + Gunicorn | 8000 |
| nginx | Reverse proxy + SSL | 80, 443 |
| redis | Брокер Celery | 6379 |
| celery-worker | Обработка задач | — |
| celery-beat | Расписание задач | — |
| flower | Мониторинг Celery | 5555 |
| litestream | Репликация SQLite в S3 | — |
| bot | Telegram-бот | — |

Все сервисы в общей bridge-сети `backend`.
