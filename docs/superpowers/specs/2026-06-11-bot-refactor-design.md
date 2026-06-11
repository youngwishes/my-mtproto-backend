# Bot Refactor Design

**Date:** 2026-06-11
**Scope:** `bot/src/` — domain-driven restructuring

## Problem

The current bot has a flat structure that doesn't scale:

- `handlers.py` — 339 lines, 14 handlers for all domains in one file, duplicated keyboard construction code
- `services/` — 8 files in a flat directory, 3 of them near-identical copy-paste (identical `except` block)
- `messages.py`, `enums.py` — global files mixing concerns from multiple domains
- `bot.py` — mixes Bot instance, Dispatcher, router registration, and entry point

## Goals

- Isolate each business domain into an independent module
- Eliminate duplicated HTTP/error-handling code via a shared transport layer
- Keep each file focused and small (~50-80 lines per handler file)
- Match the Django-side conventions: frozen dataclasses, factory functions, `@final`

## Directory Structure

```
bot/src/
├── core/
│   ├── __init__.py
│   ├── config.py           # moved from src/config.py
│   ├── exceptions.py       # moved from src/exceptions.py
│   ├── handle_error.py     # moved from src/services/handle_error.py
│   └── backend_client.py   # new — shared HTTP transport
│
├── domains/
│   ├── free_trial/
│   │   ├── __init__.py
│   │   ├── client.py       # FreeTrialClient + FreeLink schema + get_free_trial_client()
│   │   ├── handlers.py     # cmd_start, cmd_start_inline, process_boost_free, process_info
│   │   ├── messages.py     # WELCOME_TEXT_*, FREE_AVAILABLE_TEXT_MAPPING, FAQ_TEXT
│   │   └── enums.py        # FreeAvailable enum
│   │
│   ├── payments/
│   │   ├── __init__.py
│   │   ├── client.py       # PaymentsClient + schemas + get_payments_client()
│   │   ├── handlers.py     # process_boost_paid, process_pay_yukassa, process_pay_stars,
│   │   │                   # process_pre_checkout_query, process_successful_payment
│   │   └── messages.py
│   │
│   ├── referrals/
│   │   ├── __init__.py
│   │   ├── client.py       # ReferralsClient + schemas + get_referrals_client()
│   │   ├── handlers.py     # process_referral, process_referral_link
│   │   └── messages.py     # REFERRAL_CABINET text
│   │
│   └── links/
│       ├── __init__.py
│       ├── client.py       # LinksClient + schemas + get_links_client()
│       ├── handlers.py     # update_link
│       └── messages.py     # KEY_UPDATED_TEXT, KEY_GENERATED_TEXT
│
├── bot.py                  # Bot instance only
├── router.py               # central router registration
└── main.py                 # entry point, starts polling
```

**Removed:** `src/services/` directory entirely, `src/enums.py`, `src/messages.py`.

## Core Layer

### `core/backend_client.py`

Single responsibility: HTTP transport with auth headers and unified error parsing. No domain knowledge.

```python
@final
@dataclass(kw_only=True, slots=True, frozen=True)
class BackendClient:
    async def post(self, *, path: str, telegram_id: str, data: dict) -> dict:
        url = config.API_URL + path
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, data=data,
                    headers={"Bot-Auth-Token": config.BOT_AUTH_TOKEN},
                )
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            try:
                body = json.loads(exc.response.content)
            except Exception:
                raise APIError(telegram_id=telegram_id, request_url=url, error=str(exc))
            else:
                raise APIError(
                    telegram_id=telegram_id, request_url=url,
                    error=str(exc), message=body.get("error"),
                )

    async def get(self, *, path: str, telegram_id: str, params: dict) -> dict:
        # same pattern with GET
```

## Domain Layer

### Domain client pattern

Each domain has one client class with named methods in domain language. The client uses `BackendClient` via composition (not inheritance). A factory function wires dependencies.

```python
# domains/free_trial/client.py

@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FreeLink:
    link: str
    expired_date: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FreeTrialClient:
    _http: BackendClient = field(default_factory=BackendClient)

    @log_service_error
    async def check_eligibility(
        self,
        *,
        telegram_id: str,
        telegram_username: str,
        invited_from_username: str | None = None,
    ) -> str:
        data = {"username": telegram_id, "telegram_username": telegram_username}
        if invited_from_username:
            data["invited_from_username"] = invited_from_username
        result = await self._http.post(
            path="/api/v1/users/check-first-free-link/",
            telegram_id=telegram_id,
            data=data,
        )
        return result["available_free_period"]

    @log_service_error
    async def activate(self, *, telegram_id: str) -> FreeLink:
        result = await self._http.post(
            path="/api/v1/users/first-free-link/",
            telegram_id=telegram_id,
            data={"username": telegram_id},
        )
        return FreeLink(**result)


def get_free_trial_client() -> FreeTrialClient:
    return FreeTrialClient()
```

Same pattern applies to `PaymentsClient`, `ReferralsClient`, `LinksClient`.

### Handler pattern

Handlers call the factory function and use the client. Each domain has its own `Router`.

```python
# domains/free_trial/handlers.py

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    client = get_free_trial_client()
    availability = await client.check_eligibility(
        telegram_id=str(message.from_user.id),
        telegram_username=message.from_user.username,
    )
    ...
```

## Router and Entry Point

**`router.py`** — only router registration:
```python
main_router = Router()
main_router.include_routers(
    free_trial_router,
    payments_router,
    referrals_router,
    links_router,
)
```

**`bot.py`** — only Bot instance (imported by handlers that need to send messages):
```python
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
```

**`main.py`** — polling entry point:
```python
async def main() -> None:
    dp = Dispatcher()
    dp.include_router(main_router)
    await dp.start_polling(bot)
```

## What Changes vs. Current Code

| Before | After |
|--------|-------|
| `services/` (8 files, copy-paste HTTP) | `core/backend_client.py` (1 transport) + 4 domain clients |
| `handlers.py` (339 lines, 14 handlers) | 4 handler files (~50-80 lines each) |
| `messages.py` (global, 123 lines) | `messages.py` per domain |
| `enums.py` (global) | `domains/free_trial/enums.py` |
| `bot.py` (everything) | `bot.py` + `router.py` + `main.py` |
| Typo: `first_moth_free.py` | Fixed: merged into `domains/free_trial/client.py` |

## Conventions

- All service/client classes: `@final`, `frozen=True`, `slots=True`, `kw_only=True`
- `from __future__ import annotations` in every file
- Factory function per domain client: `get_<domain>_client() -> <Domain>Client`
- Response schemas (DTOs) defined as frozen dataclasses in the same `client.py` file
- `@log_service_error` stays on client methods, not on `BackendClient`
