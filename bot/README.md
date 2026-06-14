# MTPRoto Telegram Bot

Aiogram 3 bot for the BeatVault MTProto proxy subscription service. All user
interaction (free trial, proxy links, referrals, payments) happens here; the
bot talks to the Django backend over its REST API.

## Architecture

```
src/
  bot.py            # Bot/Dispatcher singletons + entrypoint (python -m src.bot)
  dependencies.py   # composition root: wires domain clients from config
  error_handler.py  # global aiogram errors handler (user + admin notification)
  config.py         # pydantic-settings (validated, fail-fast)
  enums.py          # FreeAvailable, ...
  messages.py       # user-facing text templates
  keyboards.py      # InlineKeyboardMarkup builders
  exceptions.py     # BaseServiceError / APIError (docstring = user message)
  handlers/         # one Router per domain, aggregated in __init__.router
    start.py        # /start, back-to-start, info
    free_trial.py   # claim free key
    links.py        # my-servers, reissue
    referrals.py    # cabinet, reward link
    payments.py     # payment methods, invoices, checkout, fulfilment
  core/
    backend_client.py  # thin httpx client: base_url, auth header, error parsing
  domains/
    free_trial/   # check availability, claim free key
    links/        # my-servers, reissue
    referrals/    # cabinet, reward link
    payments/     # card/stars invoice, confirm purchase
```

**Layering:** handlers never touch httpx. Each domain client wraps
`BackendClient` (injected via a frozen dataclass field) and maps JSON responses
into typed DTOs. `BackendClient` raises `APIError` on failure; the global error
handler notifies the user (using the exception's docstring) and the admin.

## Commands

```bash
# Run (env vars required — see config.py)
python -m src.bot

# Tests
uv run pytest            # or: .venv/bin/python -m pytest
```

## Configuration

`src/config.py` defines a `pydantic-settings` `Settings` model, validated at
startup — a missing or malformed variable fails fast instead of surfacing later
as `token=None`. Values come from the environment (case-insensitive) or, for
local runs, a `.env` file (git-ignored, excluded from the Docker image).

Required: `TELEGRAM_BOT_TOKEN`, `API_URL`, `BOT_AUTH_TOKEN`, `MY_TELEGRAM_ID`
(int), `PROVIDER_TOKEN`.
