# VLESS VPN sales — acceptance evidence

Статус: `in_progress`

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
| Full forward migrate | exit 0, 0.48 s wall time |
| Post-migrate integrity/FK checks | `ok` / empty |
| Legacy writer insert after expand | passed; nullable new relation preserved |
| Migrated legacy row count | 10 001 including the post-expand old-writer row |
| Backup → rollback restore equality | byte-identical |
| Synthetic backup/restore SHA-256 | `ce6780904e92a80c5508663e296dc2e20196ee36029da8f8b1098cd67d0540f9` |
| Migration/preflight regression tests | 22/22 passed |

Проверенные regression suites:

```text
make test ARGS="apps.payments.tests.test_migrations apps.vpn.tests.test_vpn_migrations apps.payments.tests.test_management.test_vless_migration_preflight"
Ran 22 tests — OK
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

Будет заполнено после product-review exact backend SHA и полного acceptance
прогона AC-001…AC-013.

## Publication and smoke

R-004/R-005 evidence добавляется только после final backend commit/PR checks и
coordinated non-production smoke. PR merge и production deploy требуют отдельных
явных разрешений пользователя.
