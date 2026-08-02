# Product acceptance: Crypto Pay для всех текущих продуктов

- **Verdict:** `accepted`
- **Reviewed base / merge-base:** `265e5f45165a28648684ebf0f54e772355eb0185`
- **Reviewed head:** `c5080f7c8187bf3d3136de27566d166aa46953c2`
- **Exact reviewed range:** `265e5f45165a28648684ebf0f54e772355eb0185..c5080f7c8187bf3d3136de27566d166aa46953c2`
- **Scope Contract:** revision 10 (current implementation clarification)
- **Approved product artifacts:** `business.md` revision 2; `architecture.md` revision 2
- **Approved plan:** `plan.md` revision 10; task packets `CPAY-B1`–`CPAY-B9`
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

The three `blocking_in_scope` findings raised after earlier acceptance passes
are addressed on this head. The first two were fixed in
`8377894e6a1843dcbb044847a59797da7ad2bcbc..a2d4efac4b6be492b91954afaf515cff92ed6e62`:
official active invoices may omit paid-only fields without becoming malformed,
and activation requires exactly one successful `CREATING` → `ACTIVE`
transition before any invoice result is exposed. The PR final review then found
that the generic Nginx access log could record the webhook secret-path before
Django middleware redaction. The exact repair
`babcdbd764d28a2bb9d96ba171909412824bc8ed..c5080f7c8187bf3d3136de27566d166aa46953c2`
adds exact webhook locations with `access_log off` to both the HTTP redirect and
HTTPS Django proxy while preserving their route behavior. These repairs do not
change approved product behavior, components or non-goals; Scope revisions 9
and 10 only clarify CPAY-B5 ownership and budget for the already required
secret-path protection.

## BR traceability

| ID | Implementing code or contract | Confirming test evidence | Observable result | Status |
|---|---|---|---|---|
| BR-001 | `bot/src/keyboards.py` adds one Crypto row after the unchanged Stars row for MTProto, VPN and gift; `bot/src/handlers/payments.py` and `bot/src/handlers/vpn.py` add separate Crypto callbacks. | `bot/tests/test_handlers.py::test_stars_first_crypto_second`; unchanged Stars/legacy cases in the full 94-test bot suite. | Each current purchase screen shows Stars first and Crypto Pay second; Stars callbacks and successful-payment routing remain operational. | `passed` |
| BR-002 | `CreateOrReuseCryptoInvoiceService` maps MTProto/gift to `mtproto_30d`, VPN to `vpn_30d`, then uses `Decimal(product.price) / Decimal("100")` and two-place quantization. | `TestCreateOrReuseCryptoInvoiceService.test_maps_kind_and_converts_kopecks_exactly`; `test_expired_invoice_becomes_local_expired_and_uses_new_price_snapshot`. | Stored 9900/14900 kopecks become exactly `99.00`/`149.00` RUB; a new invoice snapshots the current product price without a crypto price or rate. | `passed` |
| BR-003 | `CryptoPayClient.create_invoice` sends `accepted_assets="USDT,TON"`; `ValidateCryptoInvoiceService` requires the exact accepted set and paid asset membership. | `TestCryptoPayClient.test_create_invoice_sends_exact_fiat_payload_without_pii`; `TestValidateCryptoInvoiceService.test_each_mismatch_returns_its_exact_safe_reason`. | Provider creation and payment acceptance are limited to USDT and TON. | `passed` |
| BR-004 | `CryptoPaymentIntent`, its live-intent partial constraint, lifecycle selectors and `CreateOrReuseCryptoInvoiceService` implement 1800-second creation, active reuse, local expiry and stale-create recovery. `activate_crypto_intent_from_provider` now returns an intent only when exactly one `CREATING` row transitions to `ACTIVE`; a lost lease maps to safe `creation_lost`. | `TestCreateOrReuseCryptoInvoiceService.test_active_invoice_is_reused_without_provider_call`; `test_validated_create_response_activates_with_matching_positive_invoice_id`; `test_stale_lease_loss_does_not_return_non_active_intent`; model uniqueness and two-request concurrency tests. | A live invoice is returned unchanged with `reused=true`; expired/failed intent can be replaced; concurrent or stale-lease loss cannot expose an invoice URL from a non-active intent and remains retryable. | `passed` |
| BR-005 | `CryptoPaymentIntent.initiator` is the stored owner; `ApplyCryptoPaymentService` supplies `intent.initiator.username` to all three existing fulfillment services and never derives ownership from webhook data. | `TestApplyCryptoPaymentService.test_each_kind_fulfills_once_for_intent_initiator`. | MTProto, VPN and gift results, including the gift code, belong to the initiator even when provider payload content is unrelated to ownership. | `passed` |
| BR-006 | `claim_crypto_intent_for_fulfillment`, the Crypto-only Payment identity constraint and atomic `ApplyCryptoPaymentService` form the exact-once gate; validation accepts timely `paid_at` after local expiry. | `TestApplyCryptoPaymentService.test_each_kind_fulfills_once_for_intent_initiator`; `TestApplyCryptoPaymentConcurrency.test_concurrent_apply_creates_one_product_and_payment`; `TestValidateCryptoInvoiceService.test_timely_provider_payment_validates_after_local_expiry`; webhook duplicate test. | Each product is fulfilled once; duplicate/concurrent delivery cannot create a second product or Payment; timely delayed payment remains fulfillable. | `passed` |
| BR-007 | `CreateCryptoInvoiceView` is protected by `BotAuthToken`; `CryptoPayWebhookView` checks secret path and HMAC-SHA256 over raw bytes before parsing; `ValidateCryptoInvoiceService` checks invoice identity, fiat, amount, status and assets. `CryptoPayClient` treats provider-paid-only `paid_asset`/`paid_at` as optional while retaining type validation when present. | Create endpoint auth, webhook auth/raw-HMAC and semantic mismatch tests; `TestCryptoPayClient.test_active_invoice_allows_omitted_paid_only_fields`; `test_malformed_provider_timestamps_raise_safe_error` includes an invalid present `paid_asset`. | Django accepts the official active-invoice shape without weakening malformed or paid-invoice validation; unauthenticated or semantically inconsistent events cannot fulfill a product. | `passed` |
| BR-008 | `notify_crypto_purchase_task` renders MTProto expiry, VPN permanent subscription URL plus expiry, or gift code, marks delivery only after send, and retries Telegram errors; reconciliation re-enqueues unnotified fulfilled intents. | All tests in `TestNotifyCryptoPurchaseTask`; `TestReconcileCryptoPaymentsService.test_unnotified_fulfilled_intent_is_enqueued_once_per_run`. | After committed fulfillment, the initiator receives the product-specific result; failed delivery remains durably recoverable. | `passed` |
| BR-009 | `reconcile_crypto_payments_task`, `ReconcileCryptoPaymentsService` and `CELERY_BEAT_SCHEDULE["reconcile-crypto-payments"]` reuse the same validation/apply path at `*/10`. | `TestReconcileCryptoPaymentsService.test_paid_unfinished_uses_same_validator_and_apply`; `test_per_invoice_failure_does_not_stop_later_paid_invoice`; `TestCryptoReconciliationSchedule.test_reconciliation_runs_every_ten_minutes`. | Every ten minutes unfinished invoices are checked; valid paid intents are applied idempotently and one item failure does not stop later items. | `passed` |
| BR-010 | Create/provider/activation failures transition or remain safely unavailable; apply failures remain/revert to `RETRYABLE`; webhook response mapping provides successful duplicate no-op and retryable 503 paths; reconciliation covers recovery. | `TestCreateOrReuseCryptoInvoiceService.test_provider_failure_marks_creating_intent_failed_and_allows_retry`; `test_stale_lease_loss_does_not_return_non_active_intent`; apply rollback/lock tests; webhook duplicate and temporary-error tests. | Users can retry invoice creation after provider failure or lost stale lease; no unsafe success payload is returned, invalid events do not fulfill, duplicates return 200, and temporary fulfillment failures remain recoverable. | `passed` |
| BR-011 | `CreateCryptoInvoiceResponseSerializer`, `CreateCryptoInvoiceOut` and bot `CryptoInvoice` expose exactly URL, decimal-safe RUB amount, expiry and reuse flag, and only after the reservation has successfully transitioned to `ACTIVE`. | Exact-four-field and reused-value API tests; bot client exact-string mapping; `test_active_invoice_allows_omitted_paid_only_fields`; `test_stale_lease_loss_does_not_return_non_active_intent`. | A valid new invoice returns `reused=false`; active reuse returns the same URL/amount/expiry with `reused=true`; activation loss returns no success body or provider URL. | `passed` |
| BR-012 | Signed semantic warnings are reduced to `reason`, `update_id`, `invoice_id`, optional local `intent_id`; Django middleware redacts the path and omits webhook headers/body; the admin task allowlists the same fields. Exact Nginx webhook regex locations disable access logging before the HTTP redirect and HTTPS Django proxy. | `TestCryptoPayWebhookView.test_each_signed_warning_logs_and_enqueues_only_safe_fields`; `TestCryptoAdminWarningTask.test_warning_transport_uses_only_allowlisted_fields`; `TestCryptoWebhookRequestLogging.test_webhook_log_omits_path_secret_headers_and_body`; `TestCryptoWebhookNginxLogging.test_nginx_disables_access_log_for_http_and_https_webhook_routes`. | Correctly signed unknown/mismatched invoices do not fulfill and produce only safe application log/admin-warning fields; the reverse proxy does not access-log either webhook route, so the secret-path is excluded before Django redaction as well. | `passed` |

## AC traceability

| ID | Requirement evidence and observed result | Status |
|---|---|---|
| AC-001 | `test_stars_first_crypto_second` covers all three row orders; the complete bot suite (94 passed) covers unchanged Stars callbacks and successful-payment routing. | `passed` |
| AC-002 | The three Crypto callbacks map to `subscription`, `vpn_subscription`, `gift_certificate`; bot client uses the existing `Bot-Auth-Token` endpoint and handlers display provider URL/expiry. Backend creation returns that URL only after an exact one-row activation; lost stale lease produces the existing safe retry path. | `passed` |
| AC-003 | Mocked provider request asserts `currency_type=fiat`, `fiat=RUB`, exact Decimal amount, `USDT,TON`, `expires_in=1800`, opaque UUID payload and absence of Telegram ID/username/email. The client additionally accepts the official active response with omitted paid-only fields and still rejects invalid types when those fields are present. | `passed` |
| AC-004 | Active reuse/new-after-expiry and stale failure paths are covered by create-service tests; model constraint and two-request `TransactionTestCase` prove one live reservation; the lost-lease DB regression proves the activation CAS must affect exactly one row before a result can be returned. | `passed` |
| AC-005 | The three-kind apply test verifies MTProto, VPN and gift fulfillment for the initiator and one post-commit notification enqueue; notification task tests verify each corresponding Telegram result. | `passed` |
| AC-006 | Duplicate apply is a no-op, concurrent apply creates one Payment/product, and a locally expired but timely paid invoice validates and fulfills. | `passed` |
| AC-007 | Secret/HMAC failure matrix, semantic mismatch matrix, safe structured warning, Django middleware redaction, reverse-proxy no-log routes and admin-warning allowlist all pass without fulfillment. | `passed` |
| AC-008 | Reconciliation selects only `ACTIVE`, `LOCAL_EXPIRED`, `RETRYABLE`, sends paid items through the same validator/apply instances, isolates retryable item failures and re-enqueues missed notifications. | `passed` |
| AC-009 | Full backend 463-test and bot 94-test integration evidence is green; targeted legacy bot Stars/YuKassa and `CreatePaymentService` regressions remain green. | `passed` |
| AC-010 | Payment/intent migration tests prove additive preservation and Crypto-only partial constraints; settings keep token/secret backend-only and support `https://testnet-pay.crypt.bot`; schedule is exactly ten minutes. Django migration/check/Compose/import gates are green. | `passed` |
| AC-011 | API tests assert the exact four fields and correct new/reuse values; bot client preserves `rub_amount` and `expires_at` as strings and handler output displays them. Official active responses may omit paid-only fields, while a lost activation transition yields no four-field success response. | `passed` |
| AC-012 | Every approved signed unknown/mismatch reason returns 200 only after a safe warning enqueue; warning and Django middleware tests exclude token, secret, signature, raw body, PII, invoice URL, gift code and VPN URL. The Nginx regression proves both the HTTP redirect and HTTPS proxy use the exact webhook regex location with `access_log off`; invalid HMAC performs neither apply nor warning. | `passed` |

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
3–10 only adjusted implementation ownership/budgets. Revision 8 allows the
final CPAY-B4 test isolation; revision 9 adds `nginx/nginx.conf` to CPAY-B5 for
the already approved secret-path logging protection; revision 10 permits the
route-specific update to the existing VPN logging test after the new unrelated
`access_log off` directives made its global count brittle. None changes
BR/AC/components/non-goals or any task packet's assigned requirement IDs.

| Packet | Reviewed range / outcome | Acceptance use |
|---|---|---|
| CPAY-B1 / CPAY-001 | `118735f..42a95fb` approved after lifecycle-negative and reservation-winner fixes. | Persistence, constraints, selectors and read-only admin evidence accepted. |
| CPAY-B2 / CPAY-002 | `42a95fb..662e3c3` approved after exact DTO schema fix. | Provider boundary/settings evidence accepted. |
| CPAY-B3 / CPAY-003 | `c87f974..049a378` approved after post-provider SQLite-lock safe-503/one-call fix. | Create/reuse/API evidence accepted. |
| CPAY-B4 / CPAY-004 | `d121928..cd27f38`, `c032e8c..fef79f0` and revision-8 `2e08cd2..35c31b2` approved after durable MT result, retry-state and test-isolation fixes. | Exact-once and notification evidence accepted. |
| CPAY-B5 / CPAY-005 | `cd27f38..635b857` approved initially; reverse-proxy repair `babcdbd764d28a2bb9d96ba171909412824bc8ed..c5080f7c8187bf3d3136de27566d166aa46953c2` independently reviewed `approved`, no findings. | Webhook/HMAC/semantic-warning evidence plus HTTP/HTTPS reverse-proxy no-log protection accepted. |
| CPAY-B6 / CPAY-006 | `fef79f0..c154ba0` approved; two direct unit-test additions deferred as non-blocking. | Reconciliation behavior accepted; deferred items remain `follow_up`. |
| CPAY-B7 / CPAY-007 | `c154ba0..188d7c5` approved. | Bot invoice client evidence accepted. |
| CPAY-B8 / CPAY-008 | `188d7c5..80f735c` approved; ignored-workspace traceability metadata noted as non-product `follow_up`. | Bot UI/callback behavior accepted. |
| CPAY-B9 / CPAY-009 | `80f735c..2e08cd2` approved after rollout and Product/Payment documentation fixes. | Documentation/deploy gate evidence accepted. |
| Final in-scope repair across CPAY-B1/B2/B3 | `8377894e6a1843dcbb044847a59797da7ad2bcbc..a2d4efac4b6be492b91954afaf515cff92ed6e62`; fresh scoped code-review verdict `approved`, no findings. | Optional provider paid-only fields and exact-one-row activation CAS evidence accepted; no task packet or product scope expansion. |

The ignored local ledger `.superpowers/sdd/plan/progress.md` was reviewed only
as process context and is not part of the shipping diff.

## Verification evidence

### Root integration evidence on exact head

- `make test` — 463 tests, `OK`.
- Exact core + VPN logging scope — 6 tests, `OK`; this includes the regression
  for both Nginx webhook locations and the preserved VPN secret-route behavior.
- `docker compose -f docker-compose.yml config --quiet` — exit 0.
- Fresh independent batch review of the Nginx repair — `approved`, no findings.
- The repair commit changes the approved plan clarification, `nginx/nginx.conf`
  and two logging test files only. Therefore the previously green bot suite
  (94 passed), Django migrations/check, compile and wiring-import gates are not
  invalidated.
- Exact diff contains no `apps/music/` changes.

### Independent acceptance checks

- Fresh `make test ARGS="apps.core.tests.test_crypto_webhook_logging
  apps.vpn.tests.test_subscription_logging"` — 6 tests, `OK`; Django system
  check clean.
- Earlier integrated acceptance evidence remains green for unchanged paths:
  targeted backend 61 tests, targeted bot 12 tests and complete bot 94 tests.
- `git diff --check` for the exact base/head range — exit 0.
- Exact head and merge-base assertions — matched the SHAs recorded above.
- Local Nginx binary is unavailable, so no runtime `nginx -t` claim is made;
  the static route regression follows the repository's existing VPN
  configuration-test pattern and Compose rendering is valid.
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

### Addressed `blocking_in_scope`

1. **Official optional paid-only fields — addressed.** `paid_asset` and
   `paid_at` are read with `.get()` so an active `createInvoice` result may omit
   them; `test_active_invoice_allows_omitted_paid_only_fields` passes. Existing
   validation still rejects an invalid present `paid_asset`, confirmed by
   `test_malformed_provider_timestamps_raise_safe_error`. Traceability:
   BR-004, BR-007, BR-010, BR-011; AC-002, AC-003, AC-004, AC-011.
2. **Lost stale-lease activation — addressed.** The activation selector returns
   an intent only when the conditional transition updates exactly one row; the
   service otherwise raises safe `CryptoInvoiceUnavailable` with
   `reason_code="creation_lost"`. The real-DB regression proves the intent stays
   `CREATE_FAILED`, provider result fields remain blank, no success output is
   returned and the provider is called once. Traceability: BR-004, BR-010,
   BR-011; AC-002, AC-004, AC-011.
3. **Nginx secret-path access logging — addressed.** The final PR review at
   `babcdbd764d28a2bb9d96ba171909412824bc8ed` found that generic Nginx logging
   preceded Django path redaction and could expose the webhook secret. The
   repair adds exact regex locations with `access_log off` for both the HTTP
   redirect and HTTPS Django proxy. The regression asserts two locations, no-log
   behavior and preserved redirect/proxy destinations; the existing VPN test
   remains route-specific. Traceability: BR-012; AC-012; architecture revision
   2 §8; CPAY-005.

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
blocker. All three post-acceptance in-scope blockers, including the PR review's
reverse-proxy secret-path leak, are addressed on the exact reviewed head.
Testnet smoke remains an explicitly recorded release-readiness item and was
correctly not substituted with a production call.
