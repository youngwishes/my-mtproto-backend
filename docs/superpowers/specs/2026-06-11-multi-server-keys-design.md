# Multi-Server Keys Design

**Date:** 2026-06-11  
**Status:** Approved

## Problem

Historically BeatVault issued one MTPRoto key per user, tied to one VDS instance. A second (backup) VDS has been added. Keys are replicated to all VDS instances on creation, but users only see a link for the primary server and are unaware of the backup.

## Goal

Let users connect to all active VDS instances so Telegram can automatically fail over to the backup server if the primary goes down.

## Key Constraints

- All VDS instances share the same `tls_domain` (FakeTLS masquerade domain).
- The same `secret`/`token` is replicated to all active VDS instances when a key is created or updated (via `add_key_to_another_vds_instances_task` / `update_key_on_another_vds_instances_task`).
- When a new VDS is added to the fleet, `migrate_vds_keys_task` replicates all active keys to it. This maintains the invariant: **an active user's key exists on all active VDS instances**.
- `VDSInstance.name` is the DNS subdomain used in proxy URLs (`{name}.beatvault.ru`).

## Chosen Approach: On-the-fly link generation

Keep `MTPRotoKey` as a single record per user. Generate proxy links for all active VDS instances at request time using the stored `token` and `tls_domain`.

This works because:
- `token` is the same on all VDS (replicated)
- `tls_domain` is the same on all VDS (confirmed)
- `VDSInstance.name` gives the correct DNS subdomain for each server

No new model, no data duplication, no per-VDS key records.

## UX Flow

### Main menu (updated)
```
⚡️ Ускорить Telegram
📡 Мои серверы          ← new; replaces 🔄 Перевыпустить ссылку
📋 Информация
🤝 Реферальный кабинет
```

### After key issuance (free / paid / referral)
```
🎉 Твой персональный ключ готов!

📝 Как активировать:
1. Нажми «Мои серверы» ниже
2. Подключи оба сервера в Telegram — при падении одного
   Telegram автоматически переключится на другой.

⏳ Действительно до: {expired_date}

[📡 Мои серверы]        ← replaces 🇳🇱 Подключиться
[🔙 Назад]
```

### «Мои серверы» screen
```
📡 Твои серверы

Подключи все серверы в Telegram — при отказе одного
Telegram автоматически переключится на другой.

⏳ Ключ действителен до: {expired_date}

[🇳🇱 Нидерланды]              ← url=tg://proxy?server=nl1.beatvault.ru&...
[🇩🇪 Германия]                 ← url=tg://proxy?server=de1.beatvault.ru&...
[🔄 Перевыпустить ссылки]
[🔙 Назад]
```

If user has no active key:
```
У тебя пока нет активного ключа.
Нажми ⚡️ Ускорить Telegram чтобы получить его.

[🔙 Назад]
```

### After «Перевыпустить ссылки»
- `callback.answer("✅ Ссылки обновлены!")` toast
- Screen re-renders as «Мои серверы» with fresh links
- `KEY_UPDATED_TEXT` message is removed

## Notification System Changes

### Problem
After payment, `CreatePaymentService` sends a notification via `SendNotificationService` using the `proxy_purchased` `NotificationTemplate` stored in Django admin. The template currently renders a `url` button ("Подключиться" → `tg://proxy?...`). The new design needs a `callback_data` button ("📡 Мои серверы") instead.

`NotificationTemplate.render()` uses `telebot` to build `InlineKeyboardMarkup`. Messages sent this way (from Django backend via `telebot.TeleBot`) still deliver `callback_query` events to the running aiogram bot — so a `callback_data="my_servers"` button in a telebot-sent message will correctly trigger the `F.data == "my_servers"` aiogram handler.

### `NotificationTemplate` — one new field (with migration)
```python
button_callback_data = models.CharField(
    "callback_data кнопки", max_length=128, blank=True, default=""
)
```

### `NotificationTemplate.render()` — updated logic
```python
if self.button_text and self.button_url:
    keyboard_rows.append(
        [InlineKeyboardButton(text=self.button_text, url=self.button_url.format(**ctx))]
    )
elif self.button_text and self.button_callback_data:
    keyboard_rows.append(
        [InlineKeyboardButton(text=self.button_text, callback_data=self.button_callback_data)]
    )
```

### `proxy_purchased` template — updated in Django admin (data change, no code)
| Field | Before | After |
|-------|--------|-------|
| `button_text` | `🇳🇱 Подключиться` | `📡 Мои серверы` |
| `button_url` | `{link}` | *(cleared)* |
| `button_callback_data` | *(not existed)* | `my_servers` |

### `CreatePaymentService` — updated context
```python
# Before
SendNotificationService(
    slug="proxy_purchased",
    context={"link": key.get_proxy_link()},
)(chat_id=int(user.username))

# After
SendNotificationService(
    slug="proxy_purchased",
    context={"expired_date": key.expired_date.date().strftime("%d.%m.%y")},
)(chat_id=int(user.username))
```

The `proxy_purchased` template text should be updated in admin to use `{expired_date}` instead of `{link}`.

## Data Model Changes

### `VDSInstance` — one new field
```python
location = models.CharField("геолокация", default="")
# example: "🇳🇱 Нидерланды"
```

One migration: `AddField` on `VDSInstance`.

### `MTPRotoKey` — one new method (no migration)
```python
def get_proxy_link_for_server(self, server_name: str) -> str:
    secret = self.get_secret_token()
    return f"tg://proxy?server={server_name}.beatvault.ru&port=443&secret={secret}"
```

Existing `get_proxy_link()` is unchanged and used by current services.

## Backend Changes

### New DTOs
`apps/vds/services/dtos/my_servers_dto.py`:
```python
@dataclass(kw_only=True, frozen=True, slots=True)
class MyServerOut(BaseServiceDTO):
    location: str
    proxy_link: str

@dataclass(kw_only=True, frozen=True, slots=True)
class MyServersOut(BaseServiceDTO):
    expired_date: str   # formatted "dd.mm.yy"
    servers: list[MyServerOut]
```

### New service
`apps/vds/services/get_my_servers_service.py`:
```python
@final
@dataclass(kw_only=True, slots=True, frozen=True)
class GetMyServersService:
    """Возвращает proxy-ссылки пользователя для всех активных VDS."""

    @log_service_error
    def __call__(self, *, username: str) -> MyServersOut:
        user = get_user_by_username(username=username)
        if user is None:
            raise KeyDoesNotExist(telegram_id=username)
        key = get_active_key(user=user)
        if key is None:
            raise KeyDoesNotExist(telegram_id=username)
        servers = [
            MyServerOut(
                location=vds.location,
                proxy_link=key.get_proxy_link_for_server(vds.name),
            )
            for vds in get_all_active_vds_instances()
        ]
        return MyServersOut(
            expired_date=key.expired_date.date().strftime("%d.%m.%y"),
            servers=servers,
        )
```

### New endpoint
`POST /api/v1/users/my-servers/`  
View: `src/apps/users/api/v1/views/my_servers_view.py`  
Auth: `Bot-Auth-Token` header  
Body: `{"username": "<telegram_id>"}`  
Response 200:
```json
{
  "expired_date": "15.07.26",
  "servers": [
    {"location": "🇳🇱 Нидерланды", "proxy_link": "tg://proxy?server=nl1.beatvault.ru&..."},
    {"location": "🇩🇪 Германия",   "proxy_link": "tg://proxy?server=de1.beatvault.ru&..."}
  ]
}
```
Response on missing/expired key: service error with user-facing message.

## Bot Changes

### New service
`bot/src/services/get_my_servers_service.py` — HTTP client calling the new endpoint, returns `list[ServerItem]`.

### Handler changes (`bot/src/handlers.py`)

| What | Before | After |
|------|--------|-------|
| Main menu | has `🔄 Перевыпустить ссылку` | replaced by `📡 Мои серверы` |
| After free/referral key issued | `🇳🇱 Подключиться` url-button | `📡 Мои серверы` callback-button |
| After payment success | `proxy_purchased` template with url-button | `proxy_purchased` template with `callback_data="my_servers"` button (configured in admin) |
| `update_link` handler | sends new message with KEY_UPDATED_TEXT | `callback.answer("✅ Ссылки обновлены!")` toast + re-renders «Мои серверы» |
| `KEY_UPDATED_TEXT` | used | removed |

### New handler `F.data == "my_servers"`
Calls `GetMyServersService`. On success: renders server list as `url` buttons. On `KeyDoesNotExist`: renders no-key message.

## Selectors

No new selectors needed. `get_all_active_vds_instances()` and `get_active_key()` already exist in `apps/vds/selectors.py`.

## Tests

### `TestGetMyServersService`
- Happy path: active key + 2 active VDS → returns 2 `MyServerOut` with correct proxy links
- No user → `KeyDoesNotExist`
- User exists, no active key → `KeyDoesNotExist`
- One VDS `is_active=False` → excluded from result

### `TestMyServersView`
- POST with valid `username` + `Bot-Auth-Token` → 200, correct JSON shape
- Missing `Bot-Auth-Token` → 403
- User without active key → error response with user-facing message

### `TestGetProxyLinkForServer`
- Unit test on `MTPRotoKey.get_proxy_link_for_server("de1")`: verify `server=de1.beatvault.ru` in URL, secret formed correctly

### `TestNotificationTemplateRender`
- `button_url` set → renders `InlineKeyboardButton` with `url`
- `button_callback_data` set → renders `InlineKeyboardButton` with `callback_data`
- Both unset → no keyboard

### `TestCreatePaymentService` (update existing)
- Verify `SendNotificationService` is called with `context={"expired_date": ...}`, not `link`

## Files to Create / Modify

**Create:**
- `src/apps/vds/services/get_my_servers_service.py`
- `src/apps/vds/services/dtos/my_servers_dto.py`
- `src/apps/users/api/v1/views/my_servers_view.py`
- `src/apps/users/api/v1/serializers/my_servers_serializer.py`
- `src/apps/vds/tests/test_get_my_servers_service.py`
- `src/apps/vds/tests/test_my_servers_view.py`
- `bot/src/services/get_my_servers_service.py`

**Modify:**
- `src/apps/notifications/models.py` — add `button_callback_data` to `NotificationTemplate`, update `render()`
- `src/apps/payments/services/create_payment_service.py` — update `SendNotificationService` context
- `src/apps/vds/models.py` — add `location` to `VDSInstance`, add `get_proxy_link_for_server` to `MTPRotoKey`
- `src/apps/vds/services/dtos/__init__.py` — export `MyServerOut`, `MyServersOut`
- `src/apps/vds/services/__init__.py` — export `GetMyServersService`
- `src/apps/users/api/v1/views/__init__.py` — export new view
- `src/apps/users/api/v1/urls.py` — register `/v1/users/my-servers/`
- `bot/src/handlers.py` — update menus, add `my_servers` handler, update `update_link` + payment handlers
- `bot/src/messages.py` — update `KEY_GENERATED_TEXT`, remove `KEY_UPDATED_TEXT`, add `MY_SERVERS_TEXT`
- `bot/src/services/__init__.py` — export `GetMyServersService`
