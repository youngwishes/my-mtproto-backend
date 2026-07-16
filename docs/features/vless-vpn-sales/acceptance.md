# VLESS VPN sales — acceptance evidence

Статус: `ready_for_product_review`

Backend branch: `codex/vless-vpn-sales`

Agent reviewed/test-deployed SHA: `20ae654fc460163fe80aa82051ea9bb22f6d664a`

Документ содержит только синтетические или безопасные агрегированные данные.
Production credentials, адреса нод, payment identity, UUID и subscription URL
здесь не фиксируются.

## R-001 — SQLite migration/rollback rehearsal

Дата: 2026-07-16. Rehearsal выполнен не на production, а на временной
production-like SQLite-копии с pre-expand schema `payments.0005`, одним
однозначным active Product и 10 000 синтетическими legacy Payment rows.
Рабочая repository DB и production DB не изменялись.

| Gate | Result |
|---|---|
| SQLite online backup и restore | passed |
| Restored backup `PRAGMA integrity_check` | `ok` |
| Restored backup `PRAGMA foreign_key_check` | empty |
| `vless_migration_preflight` | exit 0, `VLESS migration preflight passed` |
| Full forward migrate through `vpn.0005` | exit 0, 0.50 s wall time |
| Post-migrate integrity/FK checks | `ok` / empty |
| Legacy writer insert after expand | passed; nullable new relation preserved |
| Migrated legacy row count | 10 001 including the post-expand old-writer row |
| Backup → rollback restore equality | byte-identical |
| Synthetic backup/restore SHA-256 | `ce6780904e92a80c5508663e296dc2e20196ee36029da8f8b1098cd67d0540f9` |
| Migration/preflight regression tests | 23/23 passed |

Проверенные regression suites:

```text
make test ARGS="apps.payments.tests.test_migrations apps.vpn.tests.test_vpn_migrations apps.payments.tests.test_management.test_vless_migration_preflight"
Ran 23 tests — OK
```

Rehearsal также подтвердил fail-closed preflight: исходная локальная копия без
ровно одного active Product не подходит для rollout и была дополнена только в
отдельной синтетической копии. Неоднозначные production данные должны
исправляться оператором до deploy, а не миграцией.

## R-002 — documentation and agent parity

- Backend business, architecture, contracts, models, Payments/VPN runtime и
  deploy runbooks сверены с реализацией B-001…B-018.
- Agent repository проверен read-only: HEAD совпадает с
  `20ae654fc460163fe80aa82051ea9bb22f6d664a`, tracked worktree чист.
- Backend и agent закрепляют contract v1, snapshot schema 1.0, Xray `26.7.11`
  и digest
  `sha256:a1644183accdb0b5be967093fe34be756fd5de15fe2ee0206e842ae17350967f`.
- Прямой plaintext management endpoint не является публичным: допустим только
  authenticated internal bridge; внешний management channel — HTTPS.
- 3x-ui не является writer/source of truth; упоминания в docs фиксируют запрет
  authoritative mutation либо необязательный read-only diagnostic use.
- IP-адреса тестовой ноды, credentials и конкретные коммерческие цены в docs
  отсутствуют.

## R-003 — full verification and product acceptance

Дата: 2026-07-16. Проверки выполнены с default
`VPN_SALES_ENABLED=0`; внешние payment, Telegram и agent вызовы в suites
замоканы. Exact backend head и product-review verdict фиксируются immutable
PR gate, потому что tracked документ не может ссылаться на собственный commit.

| Check | Result |
|---|---|
| `make test` | 646/646 passed |
| `cd bot && uv run pytest -q` | 90/90 passed |
| Bot Ruff | passed |
| Cross-repo contract/release tests | 11/11 passed |
| `makemigrations --check --dry-run` | no changes |
| Django system check | no issues |
| Production/local Compose config | passed |
| Default sales flag, Django/bot/VPN worker | `0` / `0` / `0` in both Compose files |
| Agent exact SHA/worktree check | matched / clean |
| Secret, test-node address and diff checks | passed |

### AC traceability

| Acceptance criterion | Evidence |
|---|---|
| AC-001 | Bot VPN section and RUB/XTR actions: `bot/tests/test_handlers.py`, `bot/tests/domains/vpn/` |
| AC-002 | Intent, pre-checkout and successful receipt API/service matrix: `apps.vpn.tests.test_views`, payment intent/receipt suites |
| AC-003 | URL only after published readiness: publish-readiness, notification and bot client/handler suites |
| AC-004 | Durable receipt, retry/recovery and delayed publication: payment task, lease recovery, reconcile and readiness suites |
| AC-005 | No eligible node blocks invoice and pre-checkout: sale availability and API suites |
| AC-006 | Active renewal adds 30 days and preserves URL: fulfillment and payment application suites |
| AC-007 | Expired renewal starts from accepted payment time and preserves URL: fulfillment/lifecycle suites |
| AC-008 | Duplicate/concurrent receipt applies once: receipt identity, lease and single-writer suites |
| AC-009 | Reissue keeps subscription URL and serves old revision until new readiness: reissue, health, reconcile and subscription suites |
| AC-010 | Flag off blocks only invoice/pre-checkout; existing lifecycle remains available: API, bot config and Compose contract suites |
| AC-011 | Refund deactivation removes serving configuration idempotently and preserves audit: refund/lifecycle suites |
| AC-012 | VPN paths do not mutate MTProto/free/referral/gift state: fulfillment, bot legacy and full regression suites |
| AC-013 | Both RUB and XTR prices are required before sale: availability, intent and exact invoice DTO suites |

Product acceptance is ready for an independent `product-reviewer` against the
final candidate SHA. Any finding returns to the originating implementer and
invalidates this ready state until the full checks are repeated.

### Initial product-review remediation

Первый product-review на SHA
`64893b3eb0aecece9a77b75337b0dec971fe7c1b` вернул findings по delayed
expiration race, management/data-plane semantics, refund operator safety и
receipt retry state machine. Исправления прошли три отдельных scoped review и
новый integration review:

- expired/refunded access реактивируется отличным новым payment, при этом
  expiration formula и exact-once purchase сохраняются;
- management transport failure сохраняет подтверждённый serving, а
  authenticated disproof отзывает его без health-side promotion;
- refund выполняется только для current/latest applied VPNPurchase, требует
  signed confirmation, exact-term CAS и хранит immutable audit;
- receipt claim фиксируется отдельно, failure переводится по exact lease в
  bounded `RETRY`, Beat переочередяет только durable due work;
- admin messages и payment identity остаются безопасными.

После remediation полный backend suite содержит 646 тестов. Требуется новый
product-review на новом exact candidate SHA; предыдущий verdict не переносится.

Повторный product-review подтвердил remediation и выявил одну терминологическую
коллизию для `INCOMPATIBLE`. Canonical semantics уточнена без изменения runtime:
management contract incompatibility запрещает новые sale/readiness/mutation,
но не считается data-plane disproof для уже подтверждённого serving evidence.

## Publication and smoke

R-004/R-005 evidence добавляется только после final backend commit/PR checks и
coordinated non-production smoke. PR merge и production deploy требуют отдельных
явных разрешений пользователя.
