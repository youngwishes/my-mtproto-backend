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
| `telegram_username` | str | Username в Telegram (@username) |
| `invited_from_username` | str? | Telegram ID пригласившего |
| `referral_activated` | bool | Активировал ли свой бесплатный период (для подсчёта рефералов пригласившего) |
| `referral_link_activated_count` | SmallInt | Сколько раз забирал бесплатную реферальную ссылку |

**Свойство:** `referral_link` — формирует ссылку `{BOT_LINK}/?start={username}`.

---

## VDSInstance (apps/vds)

Прокси-сервер. Каждый VDS — отдельная машина с FastAPI + telemt.

| Поле | Тип | Описание |
|------|-----|----------|
| `name` | str (unique) | Имя сервера (используется как `node_number` в ключах) |
| `number` | SmallInt (unique) | Порядковый номер |
| `ip_address` | str (unique) | Внешний IP |
| `internal_ip_address` | str | IP в Docker-сети |
| `port` | SmallInt | Порт FastAPI (default: 8000) |
| `user_limit` | SmallInt | Максимум активных ключей (default: 200) |
| `is_keys_available` | bool | Разрешён ли выпуск ключей на сервере (default: True) |

**Менеджер:**
- `order_by_population()` — сортировка по количеству ключей среди серверов с `is_keys_available=True` (ascending)
- `get_least_populated()` — наименее нагруженный доступный сервер

**Методы:**
- `is_available()` — `True`, если количество активных ключей < `user_limit`
- `internal_url` — `http://{internal_ip_address}:{port}`
- `external_url` — `http://{ip_address}:{port}`

---

## MTPRotoKey (apps/vds)

Прокси-ключ пользователя.

| Поле | Тип | Описание |
|------|-----|----------|
| `token` | str (unique) | Секрет для подключения (32 hex) |
| `vds` | FK → VDSInstance | На каком сервере живёт ключ |
| `user` | FK → SystemUser | Владелец |
| `was_deleted` | bool | Удалён ли с VDS |
| `tls_domain` | str | Домен TLS-маскировки |
| `node_number` | str | Имя сервера (для формирования ссылки) |
| `user_notified` | bool | Уведомлён ли об истечении |
| `expired_date` | DateTimeField? | Дата истечения |
| `last_update` | DateTimeField? | Последнее обновление (для throttle перевыпуска) |

**Enum:** `FreePeriod` — WEEK (1), TWO_WEEK (2), MONTH (3).

**Менеджер:** `expired_today()` — ключи, которые истекли на сегодня.

**Методы:**
- `get_proxy_link()` — формирует `tg://proxy?server={node}.beatvault.ru&port=443&secret={secret}`
- `get_secret_token()` — `ee{token}{hex(tls_domain)}`

---

## Product (apps/payments)

Товар для Telegram Payments API.

| Поле | Тип | Описание |
|------|-----|----------|
| `title` | str | Название |
| `description` | TextField | Описание |
| `currency` | str | Валюта (default: RUB) |
| `provider_data` | TextField | JSON для YuKassa (чек, режим оплаты) |
| `send_email_to_provider` | bool | Отправлять email провайдеру |
| `need_email` | bool | Запрашивать email у пользователя |
| `price` | Decimal(10,2) | Цена в рублях |
| `stars_price` | PositiveInt | Цена в Telegram Stars (default: 60) |

---

## Payment (apps/payments)

Запись об оплате.

| Поле | Тип | Описание |
|------|-----|----------|
| `user` | FK → SystemUser | Кто заплатил |
| `key` | OneToOne → MTPRotoKey? | За какой ключ (nullable) |
| `charge_id` | str | ID платежа от провайдера |
| `provider` | str | `YUKASSA` или `STARS` |

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
| `include_payment_buttons` | bool | Прикрепить кнопку "Поддержать" (default: False) |

**Метод:** `render(context)` → `RenderedMessage(text, markup)`. Подставляет переменные, формирует InlineKeyboardMarkup из кнопки-ссылки и/или кнопки оплаты.

---

## Mailing (apps/notifications)

Рассылка по фильтру пользователей.

| Поле | Тип | Описание |
|------|-----|----------|
| `template` | FK → NotificationTemplate | Шаблон сообщения |
| `filter_type` | IntEnum | ALL_ACTIVE / EXPIRING_SOON / NOT_SUBSCRIBED |
| `filter_params` | JSONField | Параметры фильтра (напр. `days_until_expiry`) |
| `context` | JSONField | Статический контекст для шаблона |
| `context_resolver` | IntEnum | NONE / ACTIVE_KEY_LINK |
| `status` | IntEnum | DRAFT / SENDING / COMPLETED / FAILED / PARTIALLY_COMPLETED |
| `sent_at` | DateTimeField? | Время завершения рассылки |
| `sent_count` | PositiveInt | Успешно отправлено |
| `failed_count` | PositiveInt | Ошибок при отправке |

**Методы:** `mark_as_sending()`, `mark_as_completed()`, `mark_as_failed()`, `mark_as_partially_completed()`
