# Product acceptance: Crypto Pay для всех текущих продуктов

- **Verdict:** `accepted`
- **Reviewed base / merge-base:** `265e5f45165a28648684ebf0f54e772355eb0185`
- **Reviewed head:** `35c31b29f468b75407ab547acd92077aa9821ac9`
- **Exact reviewed range:** `265e5f45165a28648684ebf0f54e772355eb0185..35c31b29f468b75407ab547acd92077aa9821ac9`
- **Scope Contract:** revision 8 (current implementation clarification)
- **Approved product artifacts:** `business.md` revision 2; `architecture.md` revision 2
- **Approved plan:** `plan.md` revision 8; task packets `CPAY-B1`–`CPAY-B9`
- **Acceptance date:** 2026-08-02

## Verdict basis

The integrated result delivers the approved user scenario: Telegram Stars stays
first and Crypto Pay is second for the current 30-day MTProto, VPN and gift
products; Django creates or reuses a 30-minute RUB invoice using the stored
kopeck price and only USDT/TON; the initiator owns fulfillment; authenticated
webhook processing, conditional exact-once application, durable Telegram result
delivery and ten-minute reconciliation cover normal, duplicate, delayed and
retryable paths.

All BR-001–BR-012 and AC-001–AC-012 are verified as `passed`. No approved
non-goal is violated and no product behavior outside the approved goal was
found. There are no `blocking_in_scope` or `scope_change_request` findings.
Non-blocking review and documentation hygiene items are recorded under
`follow_up` and do not expand the current acceptance criteria.

## BR traceability

| ID | Implementing code or contract | Confirming test evidence | Observable result | Status |
|---|---|---|---|---|
| BR-001 | `bot/src/keyboards.py` adds one Crypto row after the unchanged Stars row for MTProto, VPN and gift; `bot/src/handlers/payments.py` and `bot/src/handlers/vpn.py` add separate Crypto callbacks. | `bot/tests/test_handlers.py::test_stars_first_crypto_second`; unchanged Stars/legacy cases in the full 94-test bot suite. | Each current purchase screen shows Stars first and Crypto Pay second; Stars callbacks and successful-payment routing remain operational. | `passed` |
| BR-002 | `CreateOrReuseCryptoInvoiceService` maps MTProto/gift to `mtproto_30d`, VPN to `vpn_30d`, then uses `Decimal(product.price) / Decimal("100")` and two-place quantization. | `TestCreateOrReuseCryptoInvoiceService.test_maps_kind_and_converts_kopecks_exactly`; `test_expired_invoice_becomes_local_expired_and_uses_new_price_snapshot`. | Stored 9900/14900 kopecks become exactly `99.00`/`149.00` RUB; a new invoice snapshots the current product price without a crypto price or rate. | `passed` |
| BR-003 | `CryptoPayClient.create_invoice` sends `accepted_assets="USDT,TON"`; `ValidateCryptoInvoiceService` requires the exact accepted set and paid asset membership. | `TestCryptoPayClient.test_create_invoice_sends_exact_fiat_payload_without_pii`; `TestValidateCryptoInvoiceService.test_each_mismatch_returns_its_exact_safe_reason`. | Provider creation and payment acceptance are limited to USDT and TON. | `passed` |
| BR-004 | `CryptoPaymentIntent`, its live-intent partial constraint, lifecycle selectors and `CreateOrReuseCryptoInvoiceService` implement 1800-second creation, active reuse, local expiry and stale-create recovery. | `TestCreateOrReuseCryptoInvoiceService.test_active_invoice_is_reused_without_provider_call`; `test_validated_create_response_activates_with_matching_positive_invoice_id`; `TestCryptoPaymentIntentModel.test_only_one_creating_or_active_intent_per_initiator_and_kind`; `TestCreateCryptoInvoiceConcurrency.test_two_requests_leave_one_live_reservation`. | A live invoice is returned unchanged with `reused=true`; an expired/failed one can be replaced; concurrent requests leave one live reservation. | `passed` |
| BR-005 | `CryptoPaymentIntent.initiator` is the stored owner; `ApplyCryptoPaymentService` supplies `intent.initiator.username` to all three existing fulfillment services and never derives ownership from webhook data. | `TestApplyCryptoPaymentService.test_each_kind_fulfills_once_for_intent_initiator`. | MTProto, VPN and gift results, including the gift code, belong to the initiator even when provider payload content is unrelated to ownership. | `passed` |
| BR-006 | `claim_crypto_intent_for_fulfillment`, the Crypto-only Payment identity constraint and atomic `ApplyCryptoPaymentService` form the exact-once gate; validation accepts timely `paid_at` after local expiry. | `TestApplyCryptoPaymentService.test_each_kind_fulfills_once_for_intent_initiator`; `TestApplyCryptoPaymentConcurrency.test_concurrent_apply_creates_one_product_and_payment`; `TestValidateCryptoInvoiceService.test_timely_provider_payment_validates_after_local_expiry`; webhook duplicate test. | Each product is fulfilled once; duplicate/concurrent delivery cannot create a second product or Payment; timely delayed payment remains fulfillable. | `passed` |
| BR-007 | `CreateCryptoInvoiceView` is protected by `BotAuthToken`; `CryptoPayWebhookView` checks secret path and HMAC-SHA256 over raw bytes before parsing; `ValidateCryptoInvoiceService` checks invoice identity, fiat, amount, status and assets. | `TestCryptoInvoiceView.test_create_invoice_requires_bot_auth_token`; `TestCryptoPayWebhookView.test_secret_and_hmac_fail_closed_before_parsing`; `test_hmac_uses_exact_raw_bytes_before_json_validation`; semantic mismatch matrix. | Django owns invoice creation and webhook handling; unauthenticated or semantically inconsistent events cannot fulfill a product. | `passed` |
| BR-008 | `notify_crypto_purchase_task` renders MTProto expiry, VPN permanent subscription URL plus expiry, or gift code, marks delivery only after send, and retries Telegram errors; reconciliation re-enqueues unnotified fulfilled intents. | All tests in `TestNotifyCryptoPurchaseTask`; `TestReconcileCryptoPaymentsService.test_unnotified_fulfilled_intent_is_enqueued_once_per_run`. | After committed fulfillment, the initiator receives the product-specific result; failed delivery remains durably recoverable. | `passed` |
| BR-009 | `reconcile_crypto_payments_task`, `ReconcileCryptoPaymentsService` and `CELERY_BEAT_SCHEDULE["reconcile-crypto-payments"]` reuse the same validation/apply path at `*/10`. | `TestReconcileCryptoPaymentsService.test_paid_unfinished_uses_same_validator_and_apply`; `test_per_invoice_failure_does_not_stop_later_paid_invoice`; `TestCryptoReconciliationSchedule.test_reconciliation_runs_every_ten_minutes`. | Every ten minutes unfinished invoices are checked; valid paid intents are applied idempotently and one item failure does not stop later items. | `passed` |
| BR-010 | Create failures transition to `CREATE_FAILED`; apply failures remain/revert to `RETRYABLE`; webhook response mapping provides successful duplicate no-op and retryable 503 paths; reconciliation covers recovery. | `TestCreateOrReuseCryptoInvoiceService.test_provider_failure_marks_creating_intent_failed_and_allows_retry`; apply rollback/lock tests; `TestCryptoPayWebhookView.test_valid_and_duplicate_apply_results_are_200`; `test_temporary_apply_errors_return_503_and_leave_intent_unfinished`. | Users can retry invoice creation, invalid events do not fulfill, duplicates return 200, and temporary fulfillment failures remain recoverable. | `passed` |
| BR-011 | `CreateCryptoInvoiceResponseSerializer`, `CreateCryptoInvoiceOut` and bot `CryptoInvoice` expose exactly URL, decimal-safe RUB amount, expiry and reuse flag. | `TestCryptoInvoiceView.test_new_invoice_returns_exact_four_fields`; `test_reused_invoice_returns_same_values_and_reused_true`; bot client exact-string mapping test. | A new invoice returns `reused=false`; active reuse returns the same URL/amount/expiry with `reused=true`. | `passed` |
| BR-012 | Signed semantic warnings are reduced to `reason`, `update_id`, `invoice_id`, optional local `intent_id`; middleware redacts the path and omits webhook headers/body; admin task allowlists the same fields. | `TestCryptoPayWebhookView.test_each_signed_warning_logs_and_enqueues_only_safe_fields`; `TestCryptoAdminWarningTask.test_warning_transport_uses_only_allowlisted_fields`; `TestCryptoWebhookRequestLogging.test_webhook_log_omits_path_secret_headers_and_body`. | Correctly signed unknown/mismatched invoices do not fulfill, are logged and warn the admin using safe identifiers only; secrets, raw body, PII and result URLs/codes are excluded. | `passed` |

## AC traceability

| ID | Requirement evidence and observed result | Status |
|---|---|---|
| AC-001 | `test_stars_first_crypto_second` covers all three row orders; the complete bot suite (94 passed) covers unchanged Stars callbacks and successful-payment routing. | `passed` |
| AC-002 | The three Crypto callbacks map to `subscription`, `vpn_subscription`, `gift_certificate`; bot client uses the existing `Bot-Auth-Token` endpoint and handlers display provider URL/expiry. Evidence: bot client request test, `test_crypto_callback_uses_kind_and_shows_url`, backend auth test. | `passed` |
| AC-003 | Mocked provider request asserts `currency_type=fiat`, `fiat=RUB`, exact Decimal amount, `USDT,TON`, `expires_in=1800`, opaque UUID payload and absence of Telegram ID/username/email. | `passed` |
| AC-004 | Active reuse/new-after-expiry and stale failure paths are covered by create-service tests; model constraint and two-request `TransactionTestCase` prove one live reservation. | `passed` |
| AC-005 | The three-kind apply test verifies MTProto, VPN and gift fulfillment for the initiator and one post-commit notification enqueue; notification task tests verify each corresponding Telegram result. | `passed` |
| AC-006 | Duplicate apply is a no-op, concurrent apply creates one Payment/product, and a locally expired but timely paid invoice validates and fulfills. | `passed` |
| AC-007 | Secret/HMAC failure matrix, semantic mismatch matrix, safe structured warning, middleware redaction and admin-warning allowlist all pass without fulfillment. | `passed` |
| AC-008 | Reconciliation selects only `ACTIVE`, `LOCAL_EXPIRED`, `RETRYABLE`, sends paid items through the same validator/apply instances, isolates retryable item failures and re-enqueues missed notifications. | `passed` |
| AC-009 | Full backend 460-test and bot 94-test integration evidence is green; targeted legacy bot Stars/YuKassa and `CreatePaymentService` regressions remain green. | `passed` |
| AC-010 | Payment/intent migration tests prove additive preservation and Crypto-only partial constraints; settings keep token/secret backend-only and support `https://testnet-pay.crypt.bot`; schedule is exactly ten minutes. Django migration/check/Compose/import gates are green. | `passed` |
| AC-011 | API tests assert the exact four fields and correct new/reuse values; bot client preserves `rub_amount` and `expires_at` as strings and handler output displays them. | `passed` |
| AC-012 | Every approved signed unknown/mismatch reason returns 200 only after a safe warning enqueue; warning and middleware tests exclude token, secret, signature, raw body, PII, invoice URL, gift code and VPN URL. Invalid HMAC performs neither apply nor warning. | `passed` |

## Non-goal and scope audit

| Non-goal / boundary | Evidence | Status |
|---|---|---|
| Do not replace or change Telegram Stars | Crypto is added through separate rows/callbacks; existing Stars code paths remain and full bot regression suite is green. | `preserved` |
| No assets beyond USDT/TON | Fixed provider request and strict validation contain only USDT/TON. | `preserved` |
| No own rate or crypto price | Amount comes only from the current stored Product kopecks through Decimal division; no rate client/model exists in the diff. | `preserved` |
| No recurring payments, refunds or wallet | No such model, endpoint, task or bot flow appears in the exact diff. | `preserved` |
| No new product or duration/content change | Existing `mtproto_30d` and `vpn_30d` mappings and 30-day domain services are reused; gift uses `mtproto_30d`. | `preserved` |
| No manual mark-paid | `CryptoPaymentIntentAdmin` disables add/change/delete/actions and exposes diagnostics only. | `preserved` |
| No bot payment polling or bot webhook | Bot only requests an invoice and displays its URL; payment handling remains backend-owned. | `preserved` |
| No general provider framework/new Django app/outbox/monitoring model | Implementation stays in existing payments/notifications/core/config/bot components and uses the intent as the durable ledger. | `preserved` |
| No merge or production deploy | Neither action is part of the reviewed range or this acceptance. | `preserved` |
| `apps/music/` untouched | Exact range contains no path under `src/apps/music/`. | `preserved` |

## Scope revisions, task packets and batch reviews

Product behavior remains the immutable approved revision 2. Scope revisions
3–8 only adjusted implementation ownership/budgets; revision 8 specifically
allows the final CPAY-B4 test isolation and does not change BR/AC/non-goals.

| Packet | Reviewed range / outcome | Acceptance use |
|---|---|---|
| CPAY-B1 / CPAY-001 | `118735f..42a95fb` approved after lifecycle-negative and reservation-winner fixes. | Persistence, constraints, selectors and read-only admin evidence accepted. |
| CPAY-B2 / CPAY-002 | `42a95fb..662e3c3` approved after exact DTO schema fix. | Provider boundary/settings evidence accepted. |
| CPAY-B3 / CPAY-003 | `c87f974..049a378` approved after post-provider SQLite-lock safe-503/one-call fix. | Create/reuse/API evidence accepted. |
| CPAY-B4 / CPAY-004 | `d121928..cd27f38`, `c032e8c..fef79f0` and revision-8 `2e08cd2..35c31b2` approved after durable MT result, retry-state and test-isolation fixes. | Exact-once and notification evidence accepted. |
| CPAY-B5 / CPAY-005 | `cd27f38..635b857` approved. | Webhook/HMAC/semantic-warning evidence accepted. |
| CPAY-B6 / CPAY-006 | `fef79f0..c154ba0` approved; two direct unit-test additions deferred as non-blocking. | Reconciliation behavior accepted; deferred items remain `follow_up`. |
| CPAY-B7 / CPAY-007 | `c154ba0..188d7c5` approved. | Bot invoice client evidence accepted. |
| CPAY-B8 / CPAY-008 | `188d7c5..80f735c` approved; ignored-workspace traceability metadata noted as non-product `follow_up`. | Bot UI/callback behavior accepted. |
| CPAY-B9 / CPAY-009 | `80f735c..2e08cd2` approved after rollout and Product/Payment documentation fixes. | Documentation/deploy gate evidence accepted. |

The ignored local ledger `.superpowers/sdd/plan/progress.md` was reviewed only
as process context and is not part of the shipping diff.

## Verification evidence

### Root integration evidence on exact head

- `make test` — 460 tests, `OK`.
- `cd bot && uv run pytest -q` — 94 passed.
- Django system check — no issues.
- `makemigrations --check --dry-run` — no changes; only the documented local
  unable-to-open-history-database warning occurred.
- `compileall`, production Compose config, and production wiring import — exit 0.
- Exact diff check and working-tree status — clean before acceptance creation.
- Added-line secret-pattern scan — no secret-like values.
- Exact diff contains no `apps/music/` changes.

### Independent acceptance checks

- Targeted backend acceptance command covering create/reuse, provider request,
  exact-once apply, durable notification, create API, webhook, reconciliation,
  schedule and webhook logging — 61 tests, `OK`; Django system check clean.
- Targeted bot command covering exact invoice client mapping, all three keyboard
  orders/callbacks, retry UI and legacy successful-payment routing — 12 passed.
- `git diff --check` for the exact base/head range — exit 0.
- Exact head and merge-base assertions — matched the SHAs recorded above.
- Independent added-line secret scan — no matches.
- Pre-acceptance worktree status — clean.

## Testnet smoke

**Status:** `ready, not executed — dedicated testnet credentials required`.

The dedicated testnet API token, webhook secret, smoke BotAuth token, smoke
Telegram user/local fixture values and explicit smoke runtime base URL were not
provided. Therefore no provider request was attempted. The documented smoke is
ready to create exactly one unpaid testnet invoice, record only HTTP status,
`rub_amount`, `expires_at`, `reused` and presence of an HTTPS URL, then repeat
once for `reused=true`. It must not print/store secrets or the full invoice URL
and must never pay the invoice. A production provider call is not an acceptable
substitute.

## Findings and follow-ups

### Blocking findings

None. `blocking_in_scope = 0`; `scope_change_request = 0`.

### Non-blocking `follow_up`

1. Add direct reconciliation tests for warning-DTO isolation and apply-exception
   isolation. Existing integration/service evidence verifies recovery behavior;
   these are test granularity improvements, not new acceptance criteria.
2. Add a direct assertion of the Celery reconciliation task autoretry options.
   Current task declaration and provider-failure propagation are implemented;
   this is an additional configuration unit test.
3. Preserve the ignored-workspace report's traceability metadata outside the
   shipping diff if it remains operationally useful.
4. Align `docs/MODELS.md` Product `price` unit wording with the approved and
   implemented kopeck-storage contract already stated in `business.md` and
   `docs/apps/PAYMENTS.md`. The production conversion and tests are correct;
   this pre-existing documentation inconsistency does not change behavior.
5. The exact range also adds `.worktrees/` to `.gitignore`, which is not a
   product behavior and is outside CPAY-B1–B9's final file map. Root should
   either keep it as separately authorized repository hygiene or remove/split it
   before publication; it does not affect any approved BR/AC or non-goal.

## Final product decision

`accepted`. The implementation fulfills the approved product goal with all
BR/AC passed, preserves the explicit non-goals, and has no product acceptance
blocker. Testnet smoke remains an explicitly recorded release-readiness item and
was correctly not substituted with a production call.
