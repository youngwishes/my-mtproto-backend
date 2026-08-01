# VPN MVP — архитектура

- **Статус:** approved
- **Scope revision:** 2
- **Основание:** пользователь утвердил продуктовые требования и обе части
  архитектурного дизайна. Node-agent не хранит постоянную копию профилей;
  Django остаётся единственным постоянным источником истины. Для первого MVP
  rollout пользователь отдельно принял риск публичного plaintext HTTP
  management API без host firewall; bearer token и route allowlist остаются.

## 1. Принципы MVP

1. VPN — отдельный продукт и не меняет MTProto-сценарии.
2. Django хранит подписки, credentials, срок и список VPN-нод.
3. Node-agent хранит профили только в памяти и runtime VPN-процессов.
4. Продажа не зависит от доступности VPN-нод.
5. Обычные временные ошибки покрываются ограниченными Celery retries.
6. Редкие расхождения исправляются повторным provisioning или backfill вручную.
7. В MVP нет reconcile, delivery ledger, readiness state machine, recovery worker,
   leases и автоматического self-healing.

## 2. Компоненты

### Django backend

Новое приложение `apps.vpn` отвечает за:

- `VPNSubscription` и `VPNInstance`;
- создание и продление VPN-подписки после оплаты;
- формирование subscription-ответа для HAPP;
- HTTP-клиент node-agent;
- Celery-задачи добавления и удаления профилей;
- истечение, уведомления, административную деактивацию и backfill.

`apps.payments` получает явный идентификатор товара и маршрутизирует успешный
платёж к MTProto либо VPN fulfillment. `bot/` показывает отдельное VPN-меню и
использует отдельные callback/payload, не определяя товар по тексту кнопки.

### Новый node-agent

Создаётся новый отдельный репозиторий `my-vpn-vds-instance`. Репозиторий
`my-vless-vds-instance`, его код, контракты и deploy-схема не используются.

Agent содержит:

- FastAPI management API;
- in-memory набор активных профилей;
- адаптер Xray gRPC runtime API;
- локальный HTTP auth endpoint для Hysteria 2;
- bootstrap из центрального Django при запуске;
- Docker Compose и отдельный воспроизводимый deploy.

Agent не содержит SQLite, Redis, Celery или иной постоянной БД.

### VPN runtime на ноде

На каждой ноде работают отдельные контейнеры:

- Xray с одним управляемым VLESS+REALITY inbound;
- Hysteria 2 с HTTP-аутентификацией через node-agent.

Xray management API и Hysteria auth endpoint доступны только внутри Docker
network ноды. Management proxy agent для первого MVP rollout публикуется по
публичному IPv4 без TLS и host firewall, но пропускает только health и
management routes; FastAPI продолжает требовать bearer token. VLESS WebSocket
отсутствует.

## 3. Модель данных

### `payments.Product`

Добавляется уникальный стабильный `code`. Минимально требуются:

- `mtproto_30d` — существующий MTProto-продукт;
- `vpn_30d` — VPN на 30 дней.

Заголовок, описание, цена в рублях, Stars и provider data продолжают
редактироваться через Django Admin. Стартовые цены VPN — 149 ₽ и 149 ⭐.

### `payments.Payment`

В `PaymentKindEnum` добавляется VPN-покупка. VPN-платёж сохраняется с
пользователем, provider, charge ID и VPN kind; `key` остаётся `NULL`.

Уникальность `(provider, charge_id, kind)` для VPN kind и транзакционный сервис
не позволяют применить одну успешную оплату повторно. Старая MTProto-обработка
остаётся отдельной веткой и не меняет своё поведение.

### `vpn.VPNSubscription`

Модель наследуется от `BaseDjangoModel` и содержит:

- `user` — `OneToOneField` к `SystemUser`;
- `token` — уникальный случайный token subscription URL;
- `vless_uuid` — стабильный UUID пользователя;
- `hysteria_secret` — стабильный случайный credential;
- `expired_at` — точный срок доступа.

`token`, `vless_uuid` и `hysteria_secret` создаются один раз и не меняются при
продлении или покупке после истечения. Рабочей считается активная запись с
`expired_at > now()`.

### `vpn.VPNInstance`

Модель наследуется от `BaseDjangoModel` и содержит только необходимые данные:

- имя, номер сортировки и отображаемую локацию;
- management URL node-agent;
- публичный hostname;
- VLESS port, REALITY SNI, public key и short ID;
- Hysteria port, SNI и публичные параметры obfuscation.

Приватный REALITY key, TLS private key и management bearer token в модели не
хранятся. Общий management token задаётся backend и agent через environment.
Новая нода до ручной подготовки сохраняется с `is_active=False`.

Отдельные delivery/readiness/backfill модели не создаются.

## 4. Платёж и lifecycle подписки

### Первая покупка

1. Бот запрашивает `Product(code="vpn_30d")`.
2. Invoice payload однозначно обозначает VPN и способ оплаты.
3. Successful payment передаёт backend пользователя, provider, charge ID и
   VPN product code.
4. В одной транзакции backend проверяет idempotency, создаёт `Payment` и
   `VPNSubscription` со сроком `now + 30 days`.
5. После commit backend ставит provisioning-задачи для активных нод.
6. Бот сразу показывает срок, стабильную subscription URL и краткую инструкцию
   HAPP, не ожидая node-agent.

### Продление

Для активной подписки:

```text
expired_at = expired_at + 30 days
```

Для истёкшей или административно деактивированной:

```text
is_active = true
expired_at = payment_accepted_at + 30 days
```

Credentials и token сохраняются. После commit снова запускается provisioning
на все активные ноды.

### Истечение

Периодическая Celery-задача выбирает фактически истёкшие активные подписки,
деактивирует их и ставит удаление профиля со всех активных нод. Отдельные задачи
уведомляют пользователя за сутки, за час и после отключения. Кнопки ведут в
VPN-продление.

### Административная деактивация

Единственное специальное действие над подпиской:

1. идемпотентно устанавливает `is_active=False`;
2. немедленно прекращает выдачу рабочей subscription-конфигурации;
3. после commit ставит удаление профиля со всех активных нод.

## 5. Subscription endpoint

Публичный endpoint имеет вид:

```text
GET /api/v1/vpn/subscriptions/<token>/
```

Token содержит достаточную случайность и является единственным credential
этого endpoint. Он не должен попадать в application/access logs.

Поведение:

- неизвестный token — `404`;
- истёкшая или деактивированная подписка — `200` с пустой subscription;
- активная подписка — `200 text/plain` с Base64 от UTF-8 списка URI, по одному
  URI на строку;
- если активных нод нет, возвращается валидная пустая subscription.

Для каждой активной `VPNInstance` генератор детерминированно добавляет:

1. `vless://` с UUID пользователя и публичными REALITY-параметрами ноды;
2. `hysteria2://` с credential пользователя и публичными Hysteria-параметрами.

Ноды сортируются по номеру. Ответ содержит `Cache-Control: private, no-store`
и `X-Content-Type-Options: nosniff`. Endpoint не выполняет provisioning и не
изменяет БД.

## 6. Контракт node-agent

Management endpoints защищены bearer token и принимают JSON.

### Добавление или восстановление

```text
PUT /api/v1/profiles/<access_id>
{
  "vless_uuid": "<uuid>",
  "hysteria_secret": "<secret>"
}
```

Операция является idempotent upsert:

1. добавляет или обновляет пользователя управляемого Xray inbound;
2. только после успеха Xray публикует профиль в in-memory наборе, используемом
   Hysteria auth;
3. возвращает `200` после применения обоих шагов.

Повтор идентичного запроса безопасен.

### Удаление

```text
DELETE /api/v1/profiles/<access_id>
```

Agent удаляет запись из памяти и пользователя из Xray. Отсутствующий профиль
считается успешно удалённым; ответ — `204`.

### Health

```text
GET /health
```

Проверяет процесс agent и доступность Xray management API. Endpoint не
сравнивает набор профилей с Django.

### Hysteria auth

Hysteria обращается к отдельному локальному endpoint agent. Agent сравнивает
предъявленный credential с in-memory профилями и возвращает разрешение и
`access_id`. Endpoint доступен только из Docker network ноды и не публикуется.

### Bootstrap

При старте agent запрашивает защищённый backend endpoint со всеми активными
VPN-профилями, загружает их в память и применяет к Xray. Это одноразовое
восстановление runtime после запуска, а не периодический reconcile.

Если backend временно недоступен, agent остаётся unhealthy и повторяет startup
bootstrap с ограниченной задержкой. Редкое расхождение после отдельного
перезапуска только Xray исправляется ручным повтором bootstrap или provisioning.

## 7. Async delivery и ошибки

Backend ставит отдельную Celery-задачу на пару subscription/instance. Задача
вызывает idempotent `PUT` или `DELETE` с коротким timeout.

- timeout, connection error и `5xx` используют стандартный ограниченный retry;
- окончательная ошибка отправляет администратору пользователя, ноду и тип
  операции без credentials;
- `4xx` считается ошибкой контракта и сразу алертится;
- ошибка не откатывает Payment и VPNSubscription;
- отдельные persistent delivery states и recovery sweep отсутствуют.

Пользователь не получает техническое сообщение и не видит состояния
«готовится» или «ошибка».

## 8. Добавление новой ноды

1. Администратор создаёт `VPNInstance(is_active=False)`.
2. Запускает admin action backfill, который ставит idempotent `PUT` для каждой
   активной VPN-подписки только на выбранную ноду.
3. Проверяет завершение задач и при необходимости повторяет action.
4. Если во время backfill появились новые оплаты, перед активацией вручную
   повторяет action.
5. После smoke-check обоих протоколов вручную активирует ноду.

Автоматического activation gate и сложной защиты от редкой гонки оплаты с
backfill нет. Это осознанная операционная граница MVP.

## 9. Безопасность

- Subscription token, UUID, Hysteria credential и bearer token не логируются.
- Для первого MVP rollout node-agent management proxy доступен по публичному
  plaintext HTTP без host firewall. Принят риск перехвата bearer token и
  profile payload; bearer authentication и proxy route allowlist сохраняются.
- Xray gRPC API и Hysteria auth endpoint доступны только внутри ноды.
- REALITY/TLS private keys передаются node runtime через secret files и никогда
  не хранятся в Django или Git.
- Публичные параметры подключения допускается хранить в `VPNInstance`.
- API-тесты backend используют `Bot-Auth-Token`; agent использует отдельный
  management token.

## 10. Проверки

### Backend

- выбор `Product` по code и сохранение прежнего MTProto API;
- VPN payment через ЮKassa и Stars;
- повтор одного charge ID не продлевает срок второй раз;
- первая покупка, активное продление и покупка после истечения;
- генерация `2 × N` HAPP-профилей, порядок и URL encoding;
- пустая subscription для inactive/expired и отсутствие token в логах;
- provisioning/delete retry и admin alert;
- expiry, три уведомления и административная деактивация;
- повторяемый backfill выбранной неактивной ноды;
- полный regression suite MTProto.

### Bot

- кнопка и состояния VPN-меню;
- раздельные MTProto/VPN callback и invoice payload;
- оба способа оплаты и successful payment routing;
- текстовая инструкция HAPP и VPN-кнопки уведомлений.

### Node-agent

- idempotent PUT/DELETE;
- Xray adapter и startup bootstrap;
- Hysteria auth allow/deny;
- health и authentication management API;
- отсутствие credentials в логах;
- интеграционный smoke двух runtime-контейнеров.

### Ручная приёмка

Перед production проверяются импорт одной subscription URL в HAPP, оба профиля,
продление, истечение/деактивация и повторный backfill.

## 11. Deploy и rollback

Backend и новый node-agent разрабатываются и проверяются независимо, каждый в
своей feature-ветке и Pull Request. Рекомендуемый rollout:

1. развернуть agent и VPN runtime на первой ноде, не включая продажи;
2. проверить management API и оба transport;
3. развернуть backend и bot с неактивным VPN-продуктом;
4. создать `VPNInstance` неактивной, выполнить backfill/smoke и активировать;
5. настроить цены и вручную включить VPN-продукт;
6. выполнить реальную smoke-покупку и импорт в HAPP.

Merge каждого PR и production deploy требуют отдельных явных разрешений.
Rollback не удаляет уже сохранённые платежи и подписки; при инфраструктурной
ошибке продажи выключаются вручную через активность `Product`, после чего
согласуется исправление. Автоматическая rollback-логика VPN-профилей не входит
в MVP.

## 12. Трассировка

- BR-001..BR-004: разделы 2–4.
- BR-005..BR-009: разделы 3 и 5.
- BR-010..BR-012: разделы 4, 6 и 7.
- BR-013..BR-016: разделы 4 и 7.
- BR-017..BR-019: разделы 2, 3 и 8.
- AC-001..AC-003: разделы 3–5 и 10.
- AC-004..AC-006: разделы 4–6 и 10.
- AC-007..AC-009: разделы 4, 7 и 10.
- AC-010: разделы 8 и 10.
- AC-011: разделы 2, 3 и 10.

## 13. Явно отложено

Периодический reconcile, автоматический repair, delivery tracking, reissue,
лимиты устройств/трафика, статистика, автоматические refunds и дополнительные
VPN transports рассматриваются только отдельными будущими scope revisions.
