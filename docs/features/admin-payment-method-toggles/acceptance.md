# Product acceptance — global payment method toggles

- **Verdict:** accepted
- **Scope revision:** 3
- **Plan ID:** `PMT-007`
- **Accepted requirements:** approved business revision 2, BR-001–BR-006 and
  AC-001–AC-008
- **Revision 3 note:** revision 3 adds only `docs/apps/VPN.md` to the required
  documentation surface. Product behavior, BR/AC and non-goals are unchanged.
- **Acceptance date:** 2026-08-07

## Reviewed tree identity

`PMT_REVIEW_BASE_HEAD` is the committed **base HEAD** used by the reproducible
snapshot procedure; it is not used as a substitute name for the reviewed
working tree.

- `PMT_REVIEW_BASE_HEAD`:
  `c59eab0f9fb3d7ea38e38b6b76b5175468ca2ad8`
- `PMT_REVIEW_TREE_SHA256` (reviewed working-tree identity):
  `4c8a2bb787cfc67ffb1b61a68008ab7e98a6598a1fb672c7a5300e10f4c65250`
- `origin/main` used for the integrated feature diff:
  `c52147c7fc41d952645b92a7395c76d2f944f5c2`
- Integrated delta reviewed: `origin/main...PMT_REVIEW_BASE_HEAD`, 26 paths;
  every path is within the PMT-001–PMT-006 and approved feature-artifact map.

Exact `PMT_REVIEW_STATUS` (zero bytes; the block contains no lines):

```text
```

Exact untracked manifest (zero bytes; the block contains no lines):

```text
```

The hash binds the base HEAD, exact empty status, binary-safe tracked diff from
that base and the exact empty untracked manifest. `acceptance.md` is the only
excluded repository path because it is this evidence document.

## Evidence reviewed

- Approved `business.md` revision 2, approved `architecture.md` revision 3 and
  approved `plan.md` revision 3, including task packets PMT-B1–PMT-B7.
- Complete feature diff from `origin/main` through the base HEAD, including all
  production, test and current-documentation changes.
- PMT-001–PMT-006 reports and review packages. The SDD ledger records every
  batch PMT-B1–PMT-B6 as review-clean. PMT-005 recorded one already-correct
  VPN/both-active RED baseline (`11 failed, 1 passed`), then exact GREEN
  `12 passed`; this is not a product deviation.
- PMT-006 integration evidence: targeted backend `17 passed`; targeted bot
  `73 passed`; full Django `479 passed`; full bot `110 passed`; migration drift
  `No changes detected`; compileall, Compose config and `git diff --check`
  exited 0.
- Fresh acceptance rerun on the reviewed tree: targeted backend `17 passed`;
  targeted bot `73 passed`; exact `3 screens x 4 states` matrix `12 passed`;
  full Django `479 passed`; full bot `110 passed`; migration drift reported
  `No changes detected`; compileall and Compose config exited 0.

## Business-requirement traceability

| Requirement | Implementing code or contract | Confirming test/evidence | Observed result | Status |
|---|---|---|---|---|
| BR-001 — one global activity per supported method, shared by MTProxy, VPN and gift, with no per-product setting | `PaymentMethod.code` plus inherited `is_active`; `get_active_payment_method_codes`; both product routes use the same selector; all three opening handlers consume the returned tuple | `TestPaymentMethodModel`; `TestActivePaymentMethodCodes`; API two-route matrix; bot `test_payment_method_screen_matrix` | A single DB state produces the same ordered visibility input for all three screens; model has no `Product` relation | passed |
| BR-002 — admin manages only supported methods and cannot create an arbitrary method | exact model choices `stars`/`crypto_pay`; `PaymentMethodAdmin` makes code read-only and disables add, delete and actions | `TestPaymentMethodAdmin.test_payment_method_admin_exposes_only_active_toggle`; model choices test; migration seed test | Both supported seeded rows are independently editable only through `is_active`; no admin creation surface exists | passed |
| BR-003 — a change appears on the next opening without process restart | `ProductAPIView.get` invokes the selector on every GET; MTProxy/gift call `get_stars_invoice` on every opening; VPN calls `get_vpn_stars_invoice` on every opening | API `test_returns_current_payment_methods_on_sequential_gets`; bot matrix asserts exactly one product read per opening | A second GET in the same process sees the saved toggle; each screen, including `boost_paid`, fetches fresh product data | passed |
| BR-004 — no active methods gives exact unavailable text instead of payment buttons | three opening handlers select `Оплата временно недоступна`; three keyboard builders append only known active buttons and the existing Back row | bot `3 x 4` matrix, including all three empty states; unknown-method Back-only tests | Empty state has no payment callback, exact text and the correct existing Back callback on every screen | passed |
| BR-005 — future code-supported provider has one global state without per-product config or a generic plugin framework | one `PaymentMethod` row shape; explicit backend allowlist/order and explicit bot mapping; no product FK, provider registry or dynamic callback construction | model field/relation test; selector unknown-code exclusion; keyboard unknown-code exclusion | Extension remains an explicit supported-code change with one global boolean; unknown/arbitrary codes do not become providers | passed |
| BR-006 — migration preserves current visibility and order | migration `0008_payment_method` seeds `stars` and `crypto_pay` active with `get_or_create`; selector fixes Stars before Crypto Pay | `TestPaymentMethodMigration`; selector four-state/order test; API both-active response; bot both-active matrix | Fresh migration creates two active rows, repeat seed preserves saved `False`, and both-active screens remain Stars then Crypto Pay | passed |

## Acceptance-criterion traceability

| Criterion | Implementing code or contract | Confirming test/evidence | Observed result | Status |
|---|---|---|---|---|
| AC-001 (BR-001, BR-002) — two independent safe admin toggles, no arbitrary third method | exact two model choices and seeded rows; `PaymentMethodAdmin.list_editable=("is_active",)`, read-only code, no add/delete/actions | admin surface test; model choices test; migration test; targeted backend `17 passed` | Stars and Crypto Pay remain separately switchable while arbitrary admin creation and code mutation are unavailable | passed |
| AC-002 (BR-001, BR-004) — identical four-state matrix on all three screens | selector fixed ordering; three explicit keyboard mappings; three opening handlers and exact zero-state | bot `test_payment_method_screen_matrix`: exact `3 x 4`, fresh `12 passed`; selector four-state test | Both, Stars-only, Crypto-only and none produce the required callbacks/order/text on MTProxy, VPN and gift | passed |
| AC-003 (BR-001) — one switch affects all screens, without product-specific values | one global model; same selector is inserted into both product routes; bot maps that field for all screen builders | model no-`Product` relation test; API `2 routes x 4 states`; bot `3 x 4` matrix | The same global tuple crosses both API routes and controls every screen; no per-product storage or filter exists | passed |
| AC-004 (BR-003) — next opening refreshes live state, including MTProxy renewal | request-time selector; `process_boost_paid`, `process_vpn` and `process_gift_certificate` each fetch product data on invocation | sequential GET test; bot matrix product-call counters; integrated code inspection of `boost_paid` | Toggle changes are visible to the next same-process GET; every new opening performs one fresh product GET, including the renewal callback | passed |
| AC-005 (BR-006) — active seed and unchanged default two-button order | idempotent data migration; fixed selector order; default API/DTO and screen mapping | migration test; selector order test with Crypto physically created first; API exact response; bot both-active cases | Both rows start active and all default screens retain Stars then Crypto Pay without admin action | passed |
| AC-006 — existing Stars/Crypto Pay purchase flows stay unchanged | feature diff changes opening/filtering and DTO mapping only; `pay_*`, `vpn_pay_*`, `gift_*`, crypto invoice, successful-payment and fulfilment bodies are unchanged | full bot `110 passed`; focused `73 passed`; existing invoice payload, crypto kind, successful-payment and fulfilment routing tests | Selecting a displayed callback still invokes the pre-existing price, invoice, confirmation and fulfilment paths | passed |
| AC-007 (BR-005) — future supported method uses one global state, not per-product config/plugin machinery | allowlisted global row design, no `Product` relation, no label/order/credentials/provider interface fields | model exact-field/relation test; selector and keyboard unknown-code tests; complete diff inspection | The contract requires explicit code support and one global row; no three-product settings or arbitrary-provider framework was introduced | passed |
| AC-008 (non-goal) — no runtime enforcement for old buttons | activity is read only in product GET/opening flow; existing payment callback bodies contain no selector or activity check | origin/main diff inspection shows no callback-body changes; full callback/payment regression suites pass | A previously rendered callback continues through its existing flow; filtering applies only when a screen is opened again | passed |

## Non-goal and scope check

| Approved boundary | Diff/evidence | Result |
|---|---|---|
| No per-product availability | `PaymentMethod` has no `Product` relation or product field; one selector serves both routes | preserved |
| No editable labels/order or arbitrary providers/plugin framework | admin edits only `is_active`; code is read-only; add/delete/actions disabled; fixed allowlists/mappings reject unknown codes | preserved |
| No new provider or credentials/runtime configuration | only Stars and Crypto Pay choices are present; no settings, environment, credential or provider-interface path changed | preserved |
| No old-button runtime activity check | existing Stars/Crypto Pay callback handlers are unchanged and do not query `PaymentMethod` | preserved |
| No price, invoice, fulfilment or purchase-result change | callback/payment bodies are outside the behavioral diff; targeted and full regression suites are green | preserved |
| No `apps/music` or `apps/notifications` change | neither path appears in `origin/main...PMT_REVIEW_BASE_HEAD` | preserved |
| No historical feature rewrite | `docs/features/cryptopay-all-products/` has no diff | preserved |
| No merge or production deploy | review occurred on `codex/admin-payment-method-toggles`; publication, merge and deploy were not performed by PMT-007 | preserved |

## Findings and verdict

- `blocking_in_scope`: none.
- `scope_change_request`: none.
- `follow_up`: none required for the approved scope.

All BR-001–BR-006 and AC-001–AC-008 are passed, every approved non-goal is
preserved, PMT-006 gates and fresh acceptance checks are green, and no confirmed
`blocking_in_scope` finding remains. Final product verdict: **accepted**.
