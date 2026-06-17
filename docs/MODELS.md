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
| `telegram_username` | str | Username в Telegram (@username); `""` если у юзера нет @username |
| `invited_from_username` | str? | Telegram ID пригласившего |
| `referral_activated` | bool | Активировал ли свой бесплатный период (для подсчёта рефералов пригласившего) |
| `referral_link_activated_count` | SmallInt | Сколько раз забирал бесплатную реферальную ссылку |

**Свойство:** `referral_link` — формирует ссылку `{BOT_LINK}/?start={username}`.

`__str__` показывает `telegram_username` либо `"-"`, если его нет.

---

## VDSInstance (apps/vds)

Прокси-сервер. Каждый VDS — отдельная машина с FastAPI + telemt.

| Поле | Тип | Описание |
|------|-----|----------|
| `name` | str (unique) | DNS-субдомен сервера в хосте proxy-URL (`{name}.beatvault.ru`), напр. `kz`, `nl` |
| `number` | SmallInt (unique) | Порядковый номер |
| `ip_address` | str (unique) | Внешний IP |
| `internal_ip_address` | str | IP в Docker-сети |
| `port` | SmallInt | Порт FastAPI (default: 8000) |
| `is_keys_available` | bool | Разрешён ли выпуск ключей на сервере (default: True) |
| `is_healthy` | bool | Сервер доступен и здоров (default: True). Сбрасывается при исчерпании ретраев доставки ключа; восстанавливается health-check тасками. |
| `location` | str | Географический регион сервера (default: "") |

**Менеджер:** `ActiveQuerySet.as_manager()` — метод `.active()`. Серверы равноправны (каждый ключ присутствует на всех), поэтому понятий «наименее нагруженный»/«домашний сервер» больше нет.

**Методы:**
- `internal_url` — `http://{internal_ip_address}:{port}`
- `external_url` — `http://{ip_address}:{port}`

---

## MTPRotoKey (apps/vds)

Прокси-ключ пользователя. **Один секрет, валидный на всём флоте** — без привязки к «домашнему» серверу. БД — источник правды; присутствие секрета на серверах — производный кэш (доставляется асинхронным пушем).

| Поле | Тип | Описание |
|------|-----|----------|
| `token` | str (unique) | Секрет для подключения (32 hex) |
| `user` | FK → SystemUser | Владелец |
| `was_deleted` | bool | Удалён ли с VDS |
| `user_notified` | bool | Уведомлён ли об истечении |
| `expired_date` | DateTimeField? | Дата истечения |
| `last_update` | DateTimeField? | Последнее обновление (для throttle перевыпуска) |

**Enum:** `FreePeriod` — WEEK (1), TWO_WEEK (2), MONTH (3).

**Менеджер:** `expired_today()` — ключи, которые истекли на сегодня.

**Методы:**
- `get_proxy_link(*, server_name)` — единственный генератор ссылки: `tg://proxy?server={server_name}.beatvault.ru&port=443&secret={secret}`. Хост зависит от имени конкретного сервера, секрет одинаков на всём флоте.
- `get_secret_token()` — `ee{token}{hex(settings.TLS_DOMAIN)}`. Домен маскировки FakeTLS берётся из `settings.TLS_DOMAIN` (одинаков на всех VDS), а не из поля модели.

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
| `stars_price` | PositiveInt | Цена в Telegram Stars (default: 80) |

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
| `button_callback_data` | str | callback_data для кнопки (опционально) |
| `include_payment_buttons` | bool | Прикрепить кнопку "Поддержать" (default: False) |

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
