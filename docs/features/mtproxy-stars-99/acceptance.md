# Product Acceptance — MTProxy Telegram Stars 99

- **Verdict:** accepted
- **Scope revision:** 2 (current; revision 1 is superseded)
- **Reviewed plan items / task packet:** `MTS99-001`, `MTS99-002` / `MTS99-B1`
- **Architecture artifact:** not required by the approved plan; no architecture
  change was in scope.

## Product outcome

The Telegram bot now consistently presents 99 ★ for the 30-day MTProxy
subscription and gift certificate. Given the approved precondition that the
saved `mtproto_30d` product already has `stars_price = 99`, both Stars purchase
paths forward a 99 XTR invoice without changing payment routing, payloads, or
successful-payment behaviour. Current test representations and public
documentation describe the same price.

## Requirement traceability

| Requirement | Implementing code or contract | Confirming test / observed result | Status |
| --- | --- | --- | --- |
| BR-001 — 30-day MTProxy subscription is displayed and invoiced at 99 ★ | `FAQ_TEXT` and `PAYMENT_METHODS_TEXT` in `bot/src/messages.py`; `payment_methods()` in `bot/src/keyboards.py`; unchanged `PaymentsClient._get_stars_invoice()` maps `stars_price` to `LabeledPrice.amount`, and `process_pay_stars` forwards that invoice. | `test_info_answers_callback` and `test_payment_screen_includes_legal_links` assert 99 ★ copy/label; `test_get_stars_invoice_maps_fields` asserts amount 99 and `XTR`; `test_pay_stars_sends_xtr_invoice` asserts forwarded 99 XTR. Relevant bot tests passed; full bot suite: 88 passed. | passed |
| BR-002 — 30-day MTProxy gift certificate is displayed and invoiced at 99 ★ as the same MTProxy product | `gift_certificate_payment_methods()` shows 99 ★; unchanged `process_gift_stars` gets the same Stars invoice and retains the gift payload. | `test_gift_certificate_screen_shows_payment_options` asserts the exact 99 ★ label; `test_gift_stars_invoice_uses_gift_payload` asserts `gift_certificate_stars`, `XTR`, and amount 99. Relevant bot tests passed; full bot suite: 88 passed. | passed |
| BR-003 — current-product test representations and documentation show 99 ★ without changing model default or saved data | `ProductQuerySet.create_test_product(stars_price=99)`; `ProductFactory.stars_price = 99`; MTProxy fixture `PRODUCT_JSON["stars_price"] = 99`; `docs/BUSINESS.md` and `docs/CONTRACTS.md` show 99. | Client mapping test passes at 99; payment product-view/model tests passed (6 tests); full Django suite: 367 passed. Diff and price audit confirm the default and historical data were not changed. | passed |
| AC-001 — subscription payment options show 99 ★ | `PAYMENT_METHODS_TEXT` and `payment_methods()` contain the exact 99 ★ text/label. | `test_payment_screen_includes_legal_links` asserts `99 ★/месяц` and exact Stars button text; full bot suite: 88 passed. | passed |
| AC-002 — subscription Stars invoice has 99 XTR | Unchanged mapping in `PaymentsClient._get_stars_invoice()` and forwarding in `process_pay_stars`; current MTProxy fixture supplies 99. | `test_get_stars_invoice_maps_fields` asserts `LabeledPrice.amount == 99`, `currency == "XTR"`; `test_pay_stars_sends_xtr_invoice` observes the sent invoice amount 99 and XTR. Full bot suite: 88 passed. | passed |
| AC-003 — gift payment option shows 99 ★ and gift Stars invoice has 99 XTR | `gift_certificate_payment_methods()` contains the exact 99 ★ label; unchanged `process_gift_stars` forwards the shared Stars invoice while retaining the gift payload. | `test_gift_certificate_screen_shows_payment_options` asserts the label; `test_gift_stars_invoice_uses_gift_payload` observes payload, XTR currency, and amount 99. Full bot suite: 88 passed. | passed |
| AC-004 — `docs/BUSINESS.md` and MTProxy example in `docs/CONTRACTS.md` show 99 Stars | The monetization row and gift rule in `docs/BUSINESS.md`, plus the existing product-response example in `docs/CONTRACTS.md`, each show 99. | Reviewed diff contains only the three approved documentation value substitutions; integration audit found no current MTProxy 80 value in these documents. | passed |
| AC-005 — backend-to-bot/API fixtures, explicit MTProxy test product, factory, and invoice checks use 99 | `PRODUCT_JSON`, `create_test_product`, and `ProductFactory` explicitly set 99; unchanged API shape and invoice mapper pass it through. | `test_get_stars_invoice_maps_fields`, subscription invoice, and gift invoice tests observe 99. Product view/model tests passed (6 tests); full bot suite: 88 passed and full Django suite: 367 passed. | passed |
| AC-006 — field default/docs remain 80; migrations and historical data/tests stay unchanged | `Product.stars_price` declaration remains `default=80`; `docs/MODELS.md`, migration `0004_alter_product_stars_price.py`, and migration test retain their historical/default 80 values. | Diff does not include `docs/MODELS.md`, migrations, or `test_migrations.py`; price audit found only these approved 80 references and the new negative handler assertion. Full Django suite: 367 passed. | passed |

## Scope, non-goals, and deviations

`MTS99-B1` is on the current `scope_revision: 2` and assigns every approved
BR/AC above. The implementation diff contains exactly the eight task-packet
implementation files; this acceptance artifact is the only additional feature
document. No migration, database write, schema/API/handler/client/payment-flow
change, RUB or VPN change, default-field change, or `apps/music` change is in
the reviewed result. Callback values and gift payloads are retained by the
passing handler tests.

There are no failed or unverified approved items, no deviation from the original
product goal, and no follow-ups.

## Evidence

- Implementation handoff reports the required RED-to-GREEN sequence for both
  plan items, then green targeted tests: handlers 43 passed, PaymentsClient 8
  passed, and backend product view/model tests 6 passed.
- Batch code review for the integrated packet: `VERDICT: approved`, no
  findings. The SDD ledger records the reviewed tracked-diff SHA-256
  `4affc3c041f87b1ba0ea5e93313dd784dbd6f2e74b29b1109e20d0fe014f5cae`.
- Root fresh verification: full bot suite 88 passed; full Django suite 367
  passed; `docker compose -f docker-compose.yml config --quiet` passed; and
  `git diff --check` was clean.
- The final price audit leaves only the approved `default=80`, its documented
  default, the historical migration/test value, and the explicit negative
  assertion that the user-visible FAQ does not contain `80 ★`.
