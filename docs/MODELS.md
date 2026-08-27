# Модели данных

## BaseDjangoModel (apps/core)

Абстрактная модель. Все бизнес-модели наследуются от неё.

| Поле | Тип | Описание |
|------|-----|----------|
| `is_active` | bool | Активна ли запись (default: True) |
| `created_at` | DateTimeField | Дата создания (auto) |
| `updated_at` | DateTimeField | Дата обновления (auto) |

Менеджер `ActiveQuerySet` добавляет метод `.active()` для фильтрации по `is_active=True`.

---

## SystemUser (apps/users)

Расширяет `AbstractUser`. Telegram ID хранится в стандартном поле `username`.

| Поле | Тип | Описание |
|------|-----|----------|
| `first_month_free_used` | bool | Использовал ли бесплатный период |
| `legal_terms_accepted` | bool | Принял соглашение и обработку персональных данных |
| `telegram_username` | str | Username в Telegram (@username); `""` если у юзера нет @username |
| `invited_from_username` | str? | Telegram ID пригласившего |
| `referral_activated` | bool | Активировал ли свой бесплатный период (для подсчёта рефералов пригласившего) |
| `referral_link_activated_count` | SmallInt | Сколько раз забирал бесплатную реферальную ссылку |
| `apple_balance` | PositiveInt | Текущий бессрочный баланс яблок, default `0`; DB constraint запрещает отрицательное значение |

**Свойство:** `referral_link` — формирует ссылку `{BOT_LINK}/?start={username}`.

`__str__` показывает `telegram_username` либо `"-"`, если его нет.
Миграция выставляет `legal_terms_accepted=true` существующим строкам; default
для новых строк — `false`.

---

## VDSInstance (apps/vds)

Прокси-сервер. Каждый VDS — отдельная машина с FastAPI + telemt.

| Поле | Тип | Описание |
|------|-----|----------|
| `hosting` | FK → Hosting? | Хостинг-провайдер сервера. Nullable для постепенного заполнения существующих записей. |
| `expired_at` | DateField? | Дата, до которой оплачен конкретный VDS-инстанс |
| `name` | str (unique) | DNS-субдомен сервера в хосте proxy-URL (`{name}.mtprotokeys.com`), напр. `kz`, `nl` |
| `tls_domain` | str | Обязательный TLS-домен для FakeTLS-secret ссылок этой VDS; без default и uniqueness constraint |
| `number` | SmallInt (unique) | Порядковый номер. Задаёт порядок отображения серверов (`Meta.ordering = ["number"]`), в т.ч. порядок кнопок в «Мои серверы». Управляется через админку. |
| `ip_address` | str (unique) | Внешний IP |
| `internal_ip_address` | str | IP в Docker-сети |
| `port` | SmallInt | Порт FastAPI (default: 8000) |
| `is_keys_available` | bool | Разрешён ли выпуск ключей на сервере (default: True) |
| `is_healthy` | bool | Сервер доступен и здоров (default: True). Сбрасывается при исчерпании ретраев доставки ключа; восстанавливается health-check тасками. |
| `location` | str | Географический регион сервера (default: "") |

**Менеджер:** `ActiveQuerySet.as_manager()` — метод `.active()`. Серверы равноправны (каждый ключ присутствует на всех), поэтому понятий «наименее нагруженный»/«домашний сервер» больше нет.

Миграция добавления `tls_domain` заполняет существующие VDS значением
`mtprotokeys.com`, создаёт DB-колонку `NOT NULL`, но не сохраняет model default.
Стандартная admin/model form требует непустое значение; raw ORM save не
запускает model validation автоматически. Одинаковые домены у нескольких VDS
допустимы.

**Методы:**
- `internal_url` — `http://{internal_ip_address}:{port}`
- `external_url` — `http://{ip_address}:{port}`

---

## Hosting (apps/vds)

Справочник хостинг-провайдеров, к которым привязаны VDS-инстансы.

| Поле | Тип | Описание |
|------|-----|----------|
| `name` | str | Название хостинга |
| `link` | URL | Ссылка на панель/сайт хостинга |

---

## ProjectServer (apps/infrastructure)

Независимая, вручную поддерживаемая через Django Admin запись о регулярной
оплате проектного сервера. Связь с `Hosting` обязательна и защищена через
`PROTECT`; связей с `VDSInstance` и `VPNInstance` нет. В напоминания попадают
только активные записи.

| Поле | Тип | Описание |
|------|-----|----------|
| `ipv4` | IPv4 (unique) | IPv4-адрес проектного сервера |
| `hosting` | FK → Hosting | Хостинг-провайдер |
| `price` | Decimal(10,2) | Положительная стоимость в месяц |
| `currency` | str | `USDT`, `RUB`, `EUR` или `USD` |
| `next_payment_date` | DateField | Дата следующего платежа |
| `description` | str (max 255) | Краткое назначение сервера |

---

## MTPRotoKey (apps/vds)

Прокси-ключ пользователя. **Один raw token, валидный на всём флоте** — без
привязки к «домашнему» серверу. БД — источник правды; присутствие raw token на
серверах — производный кэш (доставляется асинхронным пушем). Клиентский
FakeTLS-secret вычисляется отдельно для конкретной VDS и в модели не хранится.

| Поле | Тип | Описание |
|------|-----|----------|
| `token` | str (unique) | Единый raw token пользователя (32 hex), доставляемый на все VDS |
| `user` | FK → SystemUser | Владелец |
| `was_deleted` | bool | Удалён ли с VDS |
| `user_notified` | bool | Уведомлён ли об истечении |
| `expired_date` | DateTimeField? | Дата истечения |
| `last_update` | DateTimeField? | Последнее обновление (для throttle перевыпуска) |

**Enum:** `FreePeriod` — WEEK (1), TWO_WEEK (2), MONTH (3).

**Менеджер:** `expired_today()` — ключи, которые истекли на сегодня.

**Методы:**
- `get_proxy_link(*, server_name, tls_domain)` — единственный генератор ссылки: `tg://proxy?server={server_name}.mtprotokeys.com&port=443&secret={secret}`. Хост зависит только от имени сервера, а в client secret передаётся TLS-домен этой VDS.
- `get_secret_token(*, tls_domain)` — `ee{token}{hex(tls_domain)}`, где домен кодируется в UTF-8. Метод не использует глобальную настройку или fallback.

---

## Product (apps/payments)

Товар для Telegram Payments API.

| Поле | Тип | Описание |
|------|-----|----------|
| `title` | str | Название |
| `description` | TextField | Описание |
| `currency` | str | Валюта (default: RUB) |
| `price` | Decimal(10,2) | Цена в копейках (`9900` = 99 RUB) |
| `stars_price` | PositiveInt | Цена в Telegram Stars (default: 80) |

---

## PaymentMethod (apps/payments)

Глобальная доступность способа оплаты для всех продуктов. Наследует
`BaseDjangoModel`; связи с `Product` нет.

| Поле | Тип | Описание |
|------|-----|----------|
| `code` | str (unique) | Поддержанный код: `platega_sbp`, `stars` или `crypto_pay` |
| `commission_percent` | Decimal(5,2) | Глобальная комиссия способа, default `0.00`; включительный диапазон `0.00..999.99` закреплён validators и DB constraint `payment_method_commission_percent_range` |
| `is_priority` | bool | Глобальный визуальный приоритет, default `False`; сохраняется независимо от `is_active`, одновременно может быть включён у нескольких способов |
| `is_active` | inherited bool | Показывать способ на новых экранах оплаты MTProto, VPN и подарочного сертификата |
| `created_at`, `updated_at` | inherited DateTime | Стандартные служебные даты |

Django admin разрешает менять `commission_percent`, `is_active` и
`is_priority`; создание, удаление и переименование строк запрещены. Приоритет
не меняет активность, порядок, комиссию или обработку платежей. Commission
migration задаёт `platega_sbp` ставку `8.00`, не меняя сохранённый `is_active`;
если строки нет, она создаётся неактивной. Остальные способы получают default
`0.00`, а их переключатели не меняются. Selector доступности возвращает только
активные поддержанные коды в фиксированном порядке СБП → Stars → Crypto Pay;
отдельный selector ставки читает текущий процент независимо от переключателя.

---

## Payment (apps/payments)

Запись об оплате.

| Поле | Тип | Описание |
|------|-----|----------|
| `user` | FK → SystemUser | Кто заплатил |
| `key` | OneToOne → MTPRotoKey? | За какой ключ (nullable) |
| `charge_id` | str | ID платежа от провайдера |
| `provider` | str | `STARS`, `CRYPTO_PAY` или `PLATEGA` (`platega`); provider value отличается от глобального method code `platega_sbp` |
| `kind` | str | `SUBSCRIPTION`, `VPN_SUBSCRIPTION` или `GIFT_CERTIFICATE`; отличает MTProto, VPN и подарочную покупку |

Для VPN-платежа `key` остаётся `NULL`; уникальность `(provider, charge_id, kind)`
не даёт обработать один successful payment повторно.

Для `CRYPTO_PAY` partial constraint
`(provider, charge_id, kind)` защищает идентичность провайдерской оплаты без
изменения legacy строк.

---

## AppleCashbackPurchase (apps/payments)

Неизменяемый loyalty-result одной подходящей MTProxy-подписки или покупки
подарочного сертификата. Наследует `BaseDjangoModel`; число строк пользователя,
включая launch history, является completed eligible purchase count. Уровень и
ставка выводятся из count и отдельно не хранятся.

| Поле | Тип | Описание |
|------|-----|----------|
| `payment` | OneToOne → Payment | Успешный платёж и владелец результата; reverse name `apple_cashback_purchase` |
| `identity_key` | str (unique) | Детерминированная identity `provider:charge_id:kind`; для пустого legacy charge — `legacy:<payment.pk>` |
| `rate_percent` | PositiveSmallInt? | Применённая ставка; `NULL` отличает historical launch row |
| `apples_earned` | PositiveInt | Начисленные яблоки; у historical row `0` |
| `balance_after` | PositiveInt | Сохранённый баланс после покупки; у historical row `0` |
| `eligible_purchase_count_after` | PositiveInt | Порядковый count пользователя после этой покупки |
| `result_expired_at` | DateTimeField? | Сохранённый срок MTProxy результата; `NULL` у gift и historical row |

Уникальные `payment` и `identity_key` образуют exactly-once границу. Normal
post-launch row хранит данные для повторного полного API/Telegram результата.
Historical row имеет `rate_percent=NULL`, `apples_earned=0`,
`balance_after=0`, `result_expired_at=NULL`: она влияет только на count/level и
не означает ретроактивное начисление.

---

## AppleRedemption (apps/payments)

Сохранённый предпросмотр обмена и, после подтверждения, его идемпотентный
результат. Наследует `BaseDjangoModel`; обычный PK используется как
`confirmation_id`.

| Поле | Тип | Описание |
|------|-----|----------|
| `user` | FK → SystemUser | Владелец quote и яблок |
| `key` | FK → MTPRotoKey? | Выбранный собственный существующий ключ; `SET_NULL` делает удалённый quote stale |
| `apples_spent` | PositiveInt | Зафиксированный spend, кратный курсу 15; days выводятся как `apples_spent // 15` |
| `quoted_expired_at` | DateTimeField | Дата, показанная в предпросмотре |
| `new_expired_at` | DateTimeField? | Зафиксированный срок после confirm; `NULL` означает pending |
| `balance_after` | PositiveInt? | Зафиксированный остаток после confirm; `NULL` у pending |

Preview не резервирует баланс и не меняет ключ. Подтверждение заполняет оба
nullable outcome-поля в той же транзакции, что debit и key expiry; повторный
confirm читает их и не применяет эффект второй раз.

---

## CryptoPaymentIntent (apps/payments)

Локальная запись жизненного цикла Crypto Pay до и после выдачи. Содержит
инициатора, `purchase_kind`, code товара, точную `rub_amount`, публичный UUID
payload, provider invoice и timestamps оплаты, выдачи и уведомления. Result
всегда закреплён за `initiator`, а не за тем, кто оплатил URL.

Статусы: `creating`, `active`, `local_expired`, `processing`, `retryable`,
`fulfilled`, `create_failed`, `provider_expired`.

Partial constraint `(initiator, purchase_kind)` для статусов `creating` и
`active` не позволяет одному пользователю иметь два живых счёта одного вида;
уникальный provider invoice связывает intent с платежом. Переходы выполняются
условными обновлениями, а не ручным mark-paid из admin.

---

## PlategaPaymentIntent (apps/payments)

Локальная запись one-time SBP покупки через Platega. Содержит публичный UUID,
инициатора, вид покупки, code товара, полную пользовательскую `rub_amount`,
`currency=RUB` и `payment_method=2`, а также provider transaction/link/expiry и
даты выдачи и уведомления. Уменьшенная на комиссию provider amount в intent не
хранится. `payment` — nullable one-to-one связь с `Payment`; `initiator` — FK с
`PROTECT`.

Статусы: `creating`, `active`, `local_expired`, `processing`, `retryable`,
`provider_canceled`, `create_failed`, `fulfilled`. Partial constraint
`(initiator, purchase_kind)` действует только для `creating|active`; unique
provider transaction ID и one-to-one `Payment` образуют остальные identity
границы. Переходы не выполняются из admin: он показывает intent только для
диагностики и не разрешает add/change/delete.

---

## VPNSubscription (apps/vpn)

Одна VPN-подписка на `SystemUser`. Наследует `BaseDjangoModel`.

| Поле | Тип | Описание |
|------|-----|----------|
| `user` | OneToOne → SystemUser | Владелец |
| `token` | str (unique) | Непредсказуемый token текущей subscription URL; заменяется при перевыпуске |
| `vless_uuid` | UUID | Credential VLESS; заменяется при перевыпуске |
| `hysteria_secret` | str | Credential Hysteria 2; заменяется при перевыпуске |
| `expired_at` | DateTimeField | Точный срок доступа |
| `last_reissued_at` | DateTimeField? | Nullable момент последнего перевыпуска для пятиминутного cooldown |

При продлении, повторной покупке после истечения и повторной обработке платежа
token и credentials не меняются. Перевыпуск active-подписки атомарно заменяет
все три credential и записывает `last_reissued_at`, сохраняя `expired_at` и
`is_active`; `updated_at` не используется для cooldown.

## VPNInstance (apps/vpn)

VPN-нода. Наследует `BaseDjangoModel`; хранит публичные параметры VLESS+REALITY
и Hysteria 2, а также внутренний management URL. Новая нода неактивна до
подготовки и ручной активации. Private keys и bearer token в модели не хранятся.

## GiftCertificate (apps/payments)

Одноразовый подарочный сертификат на 30 дней подписки.

| Поле | Тип | Описание |
|------|-----|----------|
| `code` | str (unique) | Код формата `KEY-XXXX-XXXX` |
| `buyer` | FK → SystemUser | Кто купил сертификат |
| `payment` | OneToOne → Payment | Платёж за сертификат |
| `expires_at` | DateTimeField | До какого момента сертификат можно активировать (1 год с покупки) |
| `activated_by` | FK → SystemUser? | Кто активировал сертификат |
| `activated_at` | DateTimeField? | Когда сертификат был активирован |
| `status` | str | `CREATED`, `ACTIVATED`, `EXPIRED` |

---

## NotificationTemplate (apps/notifications)

Шаблон уведомления с поддержкой переменных и кнопок.

| Поле | Тип | Описание |
|------|-----|----------|
| `slug` | SlugField (unique) | Идентификатор шаблона |
| `title` | str | Название для админки |
| `text` | TextField | HTML-текст с `{переменными}` |
| `button_text` | str | Текст кнопки (опционально) |
| `button_url` | str | URL кнопки с `{переменными}` (опционально) |
| `button_callback_data` | str | callback_data для кнопки (опционально) |
| `include_payment_buttons` | bool | Прикрепить кнопку «⚡Продлить» (default: False) |

**Метод:** `render(context)` → `RenderedMessage(text, markup)`. Подставляет переменные, формирует InlineKeyboardMarkup из кнопки-ссылки и/или кнопки оплаты. Кнопка может быть типа URL или callback (URL имеет приоритет).

---

## Mailing (apps/notifications)

Рассылка по фильтру пользователей.

| Поле | Тип | Описание |
|------|-----|----------|
| `template` | FK → NotificationTemplate | Шаблон сообщения |
| `filter_type` | IntEnum | ALL_ACTIVE / EXPIRING_SOON / NOT_SUBSCRIBED |
| `filter_params` | JSONField | Параметры фильтра (напр. `days_until_expiry`) |
| `context` | JSONField | Статический контекст для шаблона |
| `context_resolver` | IntEnum | NONE (персональных резолверов сейчас нет; каркас оставлен на будущее) |
| `status` | IntEnum | DRAFT / SENDING / COMPLETED / FAILED / PARTIALLY_COMPLETED |
| `sent_at` | DateTimeField? | Время завершения рассылки |
| `sent_count` | PositiveInt | Успешно отправлено |
| `failed_count` | PositiveInt | Ошибок при отправке |

**Методы:** `mark_as_sending()`, `mark_as_completed()`, `mark_as_failed()`, `mark_as_partially_completed()`
