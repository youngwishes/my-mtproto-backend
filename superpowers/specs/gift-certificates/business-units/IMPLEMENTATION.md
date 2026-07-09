# Implementation: Gift Certificates

## Source

- Specification: `superpowers/specs/gift-certificates/SPEC.md`
- Business-unit index: `superpowers/specs/gift-certificates/business-units/INDEX.md`

## Unit Execution Order

1. Shared foundation from UNIT-3: certificate lifecycle model, statuses, support visibility, errors, selectors, and factories.
2. UNIT-1: certificate purchase backend endpoint and bot purchase flow.
3. UNIT-2: certificate activation backend endpoint and bot activation flow.
4. Documentation and regression verification.

UNIT-3 is implemented first because UNIT-1 and UNIT-2 both depend on one-time-use, expiry, and audit rules.

## Task Ledger

### Task 1: Certificate Lifecycle Foundation

Status: verified

Business objective: support can distinguish purchased, unused, activated, expired, and invalid certificates, and the system can enforce one-time use and 1-year pre-activation expiry.

Behavior to implement:
- Add a certificate record with code, buyer, payment, status timestamps, expiry, and optional activated user.
- Add lifecycle helpers/selectors for valid, used, expired, and unknown codes.
- Add domain errors with user-facing messages.

Tests first:
- `make test ARGS="apps.payments.tests.test_gift_certificates"` should fail because `GiftCertificate` does not exist.

Docs/contracts likely affected:
- `docs/BUSINESS.md`
- `docs/MODELS.md`
- `docs/apps/PAYMENTS.md`
- `docs/CONTRACTS.md`

Out of scope:
- Bot UI.
- Purchase endpoint.
- Activation endpoint.

Dependencies: none.

Files changed:
- `src/apps/payments/models.py`
- `src/apps/payments/migrations/0005_gift_certificates.py`
- `src/apps/payments/enums.py`
- `src/apps/payments/exceptions.py`
- `src/apps/payments/selectors.py`
- `src/apps/payments/admin.py`
- `src/apps/payments/tests/factories.py`
- `src/apps/payments/tests/test_gift_certificates.py`

Commands run:
- RED: `make test ARGS="apps.payments.tests.test_gift_certificates apps.payments.tests.test_views.test_gift_certificate_views"` failed on missing `GiftCertificate` and certificate exceptions.
- GREEN: `make test ARGS="apps.payments.tests.test_gift_certificates apps.payments.tests.test_views.test_gift_certificate_views"` passed 12 tests.
- Regression: `python manage.py makemigrations --check --dry-run --settings=config.test_settings` passed after migration alignment.

Review notes: lifecycle states, one-time use, expiry, payment kind, and admin visibility are covered. Expired status persistence was fixed after observing rollback inside `transaction.atomic()`.

### Task 2: Certificate Purchase Backend

Status: verified

Business objective: a buyer can pay for a gift certificate without extending their own subscription and receive one code.

Behavior to implement:
- Add endpoint to confirm certificate payment and return `{code}`.
- Support `yukassa` and `stars` provider values.
- Create one payment record distinguishable from regular subscription purchases.
- Do not create or extend an `MTPRotoKey` for the buyer.

Tests first:
- `make test ARGS="apps.payments.tests.test_gift_certificate_purchase apps.payments.tests.test_views.test_gift_certificate_views"` should fail on missing endpoint/service.

Docs/contracts likely affected:
- `docs/CONTRACTS.md`
- `docs/apps/PAYMENTS.md`

Out of scope:
- Activating the code.
- Buyer certificate history.

Dependencies: Task 1.

Files changed:
- `src/apps/payments/services/gift_certificates.py`
- `src/apps/payments/services/__init__.py`
- `src/apps/payments/services/dtos/gift_certificate_dtos.py`
- `src/apps/payments/services/dtos/__init__.py`
- `src/apps/payments/api/v1/serializers/gift_certificate_serializers.py`
- `src/apps/payments/api/v1/views/gift_certificate_views.py`
- `src/apps/payments/api/v1/views/__init__.py`
- `src/apps/payments/api/v1/serializers/__init__.py`
- `src/apps/payments/api/v1/urls.py`
- `src/apps/payments/services/create_payment_service.py`
- `src/apps/payments/tests/test_views/test_gift_certificate_views.py`

Commands run:
- RED included in Task 1 focused backend command; missing service and endpoint failed before implementation.
- GREEN: `make test ARGS="apps.payments.tests.test_gift_certificates apps.payments.tests.test_views.test_gift_certificate_views"` passed 12 tests.
- Regression: `make test ARGS="apps.payments"` passed 30 tests.

Review notes: purchase endpoint creates a gift certificate payment and does not issue or extend buyer keys. Existing subscription purchases are explicitly marked `subscription`.
Code review follow-up: repeated gift payment confirmation is now idempotent by `(provider, charge_id, kind)` and covered by tests.

### Task 3: Certificate Activation Backend

Status: verified

Business objective: a recipient can activate a valid certificate for exactly 30 days of access.

Behavior to implement:
- Add endpoint to activate a certificate by code.
- Extend active subscription by 30 days or issue a new 30-day key.
- Mark certificate as activated atomically.
- Reject used, expired, and unknown codes.
- Do not update free-trial or referral counters.

Tests first:
- `make test ARGS="apps.payments.tests.test_gift_certificate_activation apps.payments.tests.test_views.test_gift_certificate_views"` should fail on missing activation behavior.

Docs/contracts likely affected:
- `docs/CONTRACTS.md`
- `docs/BUSINESS.md`

Out of scope:
- Refunds.
- Recipient locking.

Dependencies: Tasks 1 and 2.

Files changed:
- `src/apps/payments/services/gift_certificates.py`
- `src/apps/payments/tests/test_gift_certificates.py`
- `src/apps/payments/tests/test_views/test_gift_certificate_views.py`

Commands run:
- RED included in Task 1 focused backend command; missing activation behavior failed before implementation.
- GREEN: `make test ARGS="apps.payments.tests.test_gift_certificates apps.payments.tests.test_views.test_gift_certificate_views"` passed 12 tests.
- Regression: `make test ARGS="apps.vds.tests.test_services.test_issue_key_service apps.payments.tests.test_extend_key_service apps.users.tests.test_first_free_link apps.vds.tests.test_get_my_servers_service"` passed 20 tests.

Review notes: activation extends active keys, issues new keys when needed, rejects used/expired/unknown codes, and leaves free-trial/referral flags untouched.
Code review follow-up: activation now atomically reserves `created` certificates before granting access, rejects reservation races, and defers new-key VDS push until the activation transaction commits.

### Task 4: Bot Purchase And Activation Flow

Status: verified

Business objective: users can buy a gift certificate in the bot and recipients can activate `KEY-XXXX-XXXX` codes.

Behavior to implement:
- Add gift option to bot menu.
- Send separate YuKassa and Stars invoices with gift payloads.
- Route successful gift payments to certificate purchase confirmation.
- Show the buyer the generated code and forwarding copy.
- Accept `KEY-XXXX-XXXX` messages and activate certificates.

Tests first:
- `cd bot && uv run pytest tests/test_handlers.py tests/domains/payments/test_client.py` should fail on missing gift flow.

Docs/contracts likely affected:
- Bot-facing behavior in `docs/CONTRACTS.md`.

Out of scope:
- Certificate status cabinet.
- Rich visual gift cards.

Dependencies: Tasks 2 and 3.

Files changed:
- `bot/src/domains/payments/client.py`
- `bot/src/domains/payments/__init__.py`
- `bot/src/handlers/payments.py`
- `bot/src/keyboards.py`
- `bot/src/messages.py`
- `bot/tests/domains/payments/test_client.py`
- `bot/tests/test_handlers.py`

Commands run:
- RED: `cd bot && uv run pytest tests/test_handlers.py tests/domains/payments/test_client.py` failed on missing gift DTOs and handlers.
- GREEN: `cd bot && uv run pytest tests/test_handlers.py tests/domains/payments/test_client.py` passed 37 tests.
- Regression: `cd bot && uv run pytest` passed 63 tests.

Review notes: successful payment routing now uses invoice payload to separate subscription purchases from gift certificate purchases. `KEY-XXXX-XXXX` text messages activate certificates.
Code review follow-up: YuKassa gift invoices now rewrite receipt provider data so fiscal item description matches the gift certificate product.

### Task 5: Documentation And Final Verification

Status: verified

Business objective: project docs describe the new business rules, contracts, and models.

Behavior to implement:
- Update business, model, payment app, and API contract docs.
- Run focused backend and bot tests.
- Run broader regression command if feasible.

Tests first:
- Documentation is verified by review, not by a new test unless existing doc tests require updates.

Docs/contracts likely affected:
- `docs/BUSINESS.md`
- `docs/MODELS.md`
- `docs/apps/PAYMENTS.md`
- `docs/CONTRACTS.md`

Out of scope:
- Commit, push, or deploy unless separately requested.

Dependencies: Tasks 1-4.

Files changed:
- `docs/BUSINESS.md`
- `docs/CONTRACTS.md`
- `docs/MODELS.md`
- `docs/apps/PAYMENTS.md`

Commands run:
- `make test` passed 264 tests.
- `python manage.py makemigrations --check --dry-run --settings=config.test_settings` initially failed with a generated `0006`; migration was corrected and the command then passed.
- Final fresh verification: `make test` passed 264 tests.
- Final fresh verification: `python manage.py makemigrations --check --dry-run --settings=config.test_settings` reported `No changes detected`.
- Final fresh verification: `cd bot && uv run pytest` passed 63 tests.
- Final fresh verification: `git diff --check` passed.
- Post-review final verification: `make test` passed 267 tests.
- Post-review final verification: `python manage.py makemigrations --check --dry-run --settings=config.test_settings` reported `No changes detected`.
- Post-review final verification: `cd bot && uv run pytest` passed 63 tests.
- Post-review final verification: `git diff --check` passed.

Review notes: documentation and contract updates match the implemented backend and bot behavior.
