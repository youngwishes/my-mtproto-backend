# План реализации продажи VLESS VPN-подписок

## Статус

`approved`

План следует утверждённым [бизнес-требованиям](business.md) и
[архитектуре](architecture.md). Реализация разделена на две независимо
версионируемые delivery units:

1. новый отдельный репозиторий `my-vless-vds-instance`;
2. текущий репозиторий `my-mtproto-backend`, включая Django backend и
   Telegram-бот.

Пункты не разрешают production deploy. Главный оркестратор публикует отдельные
Pull Request, получает финальное ревью точного head SHA каждого репозитория и
останавливается перед merge/deploy согласно release gates ниже.

## Правила исполнения

- Каждый пункт выполняется через RED → GREEN → рефакторинг на зелёном тесте.
- Один `plan-implementer` получает не более двух соседних пунктов одной партии.
- После каждой партии работает отдельный `code-reviewer`; reviewer не исправляет
  собственные замечания.
- Партии по умолчанию последовательны. Параллельность разрешена только там, где
  она явно указана и файлы/зависимости не пересекаются.
- Пути с префиксом **`[NEW REPO]`** принадлежат будущему отдельному репозиторию
  `my-vless-vds-instance`; его нельзя создавать внутри backend-репозитория.
- Agent contract v1 фиксируется до runtime-кода. Agent проходит реализацию,
  review и test deploy до включения backend mutation integration.
- Исправление management transport проходит двухступенчатый A-010: immutable
  direct-bridge bootstrap без loopback rollback, затем final SHA с bootstrap как
  единственным проверенным rollback target.
- `VPN_SALES_ENABLED` остаётся `False` до совместной приёмки release pair.

## Фаза C — общий контракт и границы репозиториев

Фаза выполняется первой и является общим checkpoint. В ней два пункта; одна
последовательная партия `C-001..C-002`.

### C-001 — Зафиксировать contract v1 и canonical fixtures

- **Результат:** машиночитаемый exact-snapshot contract v1, одинаковые canonical
  JSON/hash fixtures и таблица HTTP-ответов для backend и agent.
- **BR/AC:** BR-006, BR-007, BR-008, BR-012, BR-014; AC-003, AC-004, AC-008.
- **Зависимости:** утверждённые `business.md` и `architecture.md`; других пунктов
  нет.
- **Файлы и владение:**
  - backend: `docs/features/vless-vpn-sales/contracts/agent-v1.openapi.yaml`,
    `docs/features/vless-vpn-sales/contracts/snapshot-v1.schema.json`,
    `docs/features/vless-vpn-sales/contracts/fixtures/*.json`,
    `docs/features/vless-vpn-sales/contracts/tests/`;
  - контракт содержит только `GET /api/v1/health`, `GET /api/v1/snapshot`,
    `PUT /api/v1/snapshot`, schema/contract version, revision/hash, sorted
    `accesses[]`, `409/413/426` и безопасные error codes.
- **RED:** schema/fixture test доказывает, что несортированный snapshot,
  неверный SHA-256, incremental endpoint, unknown major version и одинаковая
  revision с другим hash не проходят контракт.
- **Минимальное production-изменение:** production-кода нет; только backend-owned
  canonical contract source и fixtures.
- **Документация:** compatibility matrix v1, canonicalization rules, лимиты
  entries/bytes и запрет incremental mutations.
- **Проверка:** `python -m json.tool docs/features/vless-vpn-sales/contracts/snapshot-v1.schema.json >/dev/null && python -m unittest discover -s docs/features/vless-vpn-sales/contracts/tests`.
- **Готово, когда:** канонический источник и fixtures в backend проходят
  собственные schema/hash tests; перенос в agent и межрепозиторная parity
  проверяются только после bootstrap нового репозитория в A-002.

### C-002 — Зафиксировать cross-repo release protocol

- **Результат:** явный порядок agent-first, compatible SHA pair и отдельные
  rollback/test-deploy gates без секретов или IP в git.
- **BR/AC:** BR-006, BR-013, BR-014, BR-015, BR-018; AC-004, AC-005, AC-010,
  AC-013.
- **Зависимости:** C-001.
- **Файлы и владение:** только backend
  `docs/features/vless-vpn-sales/release-checklist.md` и его documentation test;
  agent compatibility/deploy docs появятся после bootstrap в A-008/A-010.
- **RED:** documentation/CI check падает, если release evidence не содержит
  backend SHA, agent SHA, contract/schema major, Xray version+digest, результаты
  contract tests и rollback target.
- **Минимальное production-изменение:** production-кода нет.
- **Документация:** agent PR/review → test deploy → backend integration/PR →
  controlled smoke → единый явный production permission gate; pre-VLESS backend
  не объявляется допустимым rollback после первого оплаченного receipt.
- **Проверка:** `python docs/features/vless-vpn-sales/contracts/tests/test_release_evidence.py`.
- **Готово, когда:** checklist однозначно запрещает backend mutation calls до
  reviewed/test-deployed agent и запрещает включение продаж без проверенного
  совместимого SHA pair.

## Delivery unit A — `my-vless-vds-instance`

Новый репозиторий создаётся рядом с backend, по эксплуатационным соглашениям
`my-mtproto-vds-instance`, но без копирования его секретов, inventory или
untracked-файлов. Фаза содержит десять атомарных пунктов.

### A-001 — Создать воспроизводимый каркас agent-репозитория

- **Результат:** отдельный Python 3.13/FastAPI-проект с тестами, явными exports,
  Dockerfile, Compose и безопасным `.gitignore`.
- **BR/AC:** BR-006, BR-008, BR-014; AC-004.
- **Зависимости:** C-002.
- **Файлы и владение:** root сначала через GitHub CLI создаёт публичный
  `youngwishes/my-vless-vds-instance` с минимальным server-side `README.md` и
  default branch `main`, затем клонирует его рядом с backend и создаёт
  `codex/vless-vpn-sales`; **[NEW REPO]** `.gitignore`, `.python-version`,
  `pyproject.toml`, `uv.lock`, `Makefile`, `src/app.py`, `src/config.py`,
  `src/**/__init__.py`, `tests/`, `Dockerfile`, `docker-compose.local.yml`,
  `docker-compose.yml`, `README.md`.
- **RED:** repository preflight сначала требует owner=`youngwishes`,
  visibility=`PUBLIC`, default branch=`main`, branch protection/default-main
  policy и отсутствие feature commit в `main`; smoke test затем не может
  импортировать `src.app` и требует fail-fast startup без конфигурации.
- **Минимальное production-изменение:** root включает branch protection для
  `main` до feature push; в коде — только пустое FastAPI application factory и
  typed settings, business endpoints ещё не применяют Xray.
- **Документация:** минимальный README в `main`, затем feature-branch README с
  локальным запуском, test command, layout и запретом 3x-ui как writer/source of
  truth.
- **Проверка:** root сначала выполняет
  `gh repo view youngwishes/my-vless-vds-instance`; только при подтверждённом
  `not found` создаёт `gh repo create youngwishes/my-vless-vds-instance --public --add-readme`,
  затем проверяет `gh repo view youngwishes/my-vless-vds-instance --json owner,visibility,defaultBranchRef && gh api repos/youngwishes/my-vless-vds-instance/branches/main/protection >/dev/null && test "$(git branch --show-current)" = codex/vless-vpn-sales && uv run pytest tests/unit/test_app.py -q && docker compose -f docker-compose.yml config --quiet`.
- **Готово, когда:** если repo уже существовал, root безопасно подтвердил его
  owner/public/default-main и отсутствие конфликтующего содержимого либо
  остановился без перезаписи; иначе root создал его из явного решения
  пользователя. Feature files находятся только в `codex/vless-vpn-sales`, branch
  protection/default-main проверены, прямого feature push в `main` нет. Создание
  repo не считается разрешением на merge или deploy.

### A-002 — Реализовать DTO и contract/provider tests

- **Результат:** agent валидирует contract v1 DTO, canonical JSON/hash и
  payload limits до любого обращения к Xray.
- **BR/AC:** BR-006, BR-007, BR-008, BR-012, BR-014; AC-003, AC-004, AC-008.
- **Зависимости:** A-001, C-001.
- **Файлы и владение:** **[NEW REPO]** `src/api/schemas/`,
  `src/domain/snapshot.py`, `src/exceptions.py`, `tests/contract/`,
  `docs/contracts/v1/`; reviewed C-001 source/fixtures копируются в agent с
  явной provenance/checksum, но backend-файлы этим implementer-ом не меняются.
- **RED:** provider tests на malformed UUID/access ID, duplicate access,
  unsorted input rejection, wrong hash, oversized bytes/entries и unknown
  schema/contract major.
- **Минимальное production-изменение:** immutable DTO и pure canonicalizer;
  никаких Xray side effects.
- **Документация:** canonical encoding, numeric sort, accepted limits и stable
  error DTO.
- **Проверка:** `uv run pytest tests/contract tests/unit/test_snapshot.py -q`.
- **Готово, когда:** agent provider suite побайтно совпадает с source/fixtures
  C-001 и их checksum, invalid/oversize payload отклоняется до mock Xray.

### A-003 — Добавить HTTPS bearer authentication и ротацию

- **Результат:** все agent endpoints защищены отдельным node token, current/next
  rotation и constant-time comparison; секреты редактируются в логах.
- **BR/AC:** BR-006, BR-014; AC-004.
- **Зависимости:** A-001.
- **Файлы и владение:** **[NEW REPO]** `src/security/auth.py`,
  `src/security/logging.py`, `src/config.py`, `src/app.py`,
  `tests/unit/test_auth.py`, `tests/unit/test_logging.py`, `.env.example`.
- **RED:** missing/wrong token получает `401`, token одной ноды не подходит
  другой, current+next проходят в overlap, raw Authorization отсутствует в
  captured logs.
- **Минимальное production-изменение:** FastAPI dependency с
  `secrets.compare_digest`, env lookup current/optional next и redaction filter.
- **Документация:** token generation/rotation без значений секретов; HTTPS
  termination является обязательной deploy-конфигурацией.
- **Проверка:** `uv run pytest tests/unit/test_auth.py tests/unit/test_logging.py -q`.
- **Готово, когда:** auth tests зелёные и приложение не запускается с коротким
  или пустым production token.

### A-004 — Реализовать exact-set Xray adapter

- **Результат:** один выделенный managed inbound приводится к точному набору
  UUID; неуправляемые inbounds не меняются.
- **BR/AC:** BR-006, BR-007, BR-008, BR-011, BR-014, BR-016; AC-003, AC-004,
  AC-009, AC-011.
- **Зависимости:** A-002.
- **Файлы и владение:** **[NEW REPO]** `src/xray/client.py`,
  `src/xray/exact_set_service.py`, `src/xray/dtos.py`, `src/xray/exceptions.py`,
  `tests/unit/test_exact_set_service.py`, `tests/integration/test_xray.py`.
- **RED:** tests на add/replace/remove, повторный exact set, Xray timeout/error,
  сохранение unmanaged inbound и отсутствие incremental public API.
- **Минимальное production-изменение:** injected Xray contract и frozen
  dataclass `ApplyExactSetService`; transport создаётся только factory-функцией.
- **Документация:** managed inbound ownership и поддержанная Xray API/version.
- **Проверка:** `uv run pytest tests/unit/test_exact_set_service.py tests/integration/test_xray.py -q`.
- **Готово, когда:** pinned real Xray container принимает exact set и итоговый
  managed набор равен snapshot без изменения других inbounds.

### A-005 — Сделать snapshot persistence и crash recovery атомарными

- **Результат:** snapshot сохраняется через temp+fsync+rename и безопасно
  восстанавливается после трёх определённых crash points.
- **BR/AC:** BR-006, BR-008, BR-014; AC-004.
- **Зависимости:** A-002, A-004.
- **Файлы и владение:** **[NEW REPO]** `src/storage/snapshot_store.py`,
  `src/services/apply_snapshot_service.py`, `tests/unit/test_snapshot_store.py`,
  `tests/integration/test_crash_recovery.py`.
- **RED:** injected crashes до Xray apply, после Xray apply/до rename и после
  rename/до response; torn/permission-invalid file не делает agent ready.
- **Минимальное production-изменение:** frozen service с injected Xray adapter и
  store; success только после Xray acceptance и durable rename.
- **Документация:** authoritative local-cache semantics, file permissions и
  operator recovery.
- **Проверка:** `uv run pytest tests/unit/test_snapshot_store.py tests/integration/test_crash_recovery.py -q`.
- **Готово, когда:** каждый crash test восстанавливает last durable snapshot,
  не публикует ложную readiness и допускает безопасный retry.

### A-006 — Открыть только health/snapshot endpoints с revision semantics

- **Результат:** три endpoint contract v1 возвращают runtime metadata и
  реализуют no-op/stale/conflict/overflow/incompatible поведение.
- **BR/AC:** BR-006, BR-007, BR-008, BR-012, BR-014; AC-003, AC-004, AC-008.
- **Зависимости:** A-003, A-005.
- **Файлы и владение:** **[NEW REPO]** `src/api/routes/health.py`,
  `src/api/routes/snapshot.py`, `src/services/get_health_service.py`,
  `src/services/get_snapshot_service.py`, `src/factories.py`,
  `tests/api/test_health.py`, `tests/api/test_snapshot.py`.
- **RED:** exact HTTP tests для `200/401/409/413/426`; route enumeration
  доказывает отсутствие add/update/delete endpoints; health не READY при drift.
- **Минимальное production-изменение:** thin routes и module-level factories,
  внедряющие A-005; никакой логики в handlers.
- **Документация:** OpenAPI сверяется с C-001 и содержит agent SHA, Xray version,
  applied revision/hash/readiness.
- **Проверка:** `uv run pytest tests/api tests/contract -q`.
- **Готово, когда:** provider contract suite полностью зелёный и generated
  OpenAPI не расходится с reviewed contract.

### A-007 — Закрепить Xray/REALITY runtime

- **Результат:** Compose запускает agent и Xray по immutable version+digest с
  одним VLESS+REALITY/TCP/`xtls-rprx-vision` managed inbound.
- **BR/AC:** BR-007, BR-010, BR-011; AC-003, AC-009.
- **Зависимости:** A-004, A-006.
- **Файлы и владение:** **[NEW REPO]** `docker-compose.yml`,
  `docker-compose.local.yml`, `xray/config.template.json`, `entrypoint.sh`,
  `.env.example`, `tests/integration/test_runtime.py`.
- **RED:** integration test падает при mutable/unpinned image, invalid REALITY
  target/private key, неверном flow/security или agent readiness до restore.
- **Минимальное production-изменение:** pinned image digest, read-only config,
  dropped capabilities where possible и healthchecks. Compose-owned management
  bridge имеет `internal: true`, subnet `172.31.255.0/28`, gateway
  `172.31.255.1`, фиксированные Xray `172.31.255.2` и agent `172.31.255.3`;
  agent не публикует host ports и не подключается к public/default network.
  3x-ui отсутствует.
- **Документация:** Xray upgrade policy, target/SNI TLS 1.3 preflight и запрет
  private/loopback/link-local/metadata target.
- **Проверка:** `docker compose -f docker-compose.yml config --quiet && uv run pytest tests/integration/test_runtime.py -q`.
- **Готово, когда:** pinned runtime восстанавливает empty/non-empty snapshot и
  health сообщает точную Xray version без раскрытия private key.

### A-008 — Добавить Ansible test/prod deployment и сетевую защиту

- **Результат:** воспроизводимый serial deploy полного agent SHA с HTTPS,
  firewall allowlist, Vault/env secrets, backup snapshot и совместимым rollback.
- **BR/AC:** BR-006, BR-013, BR-014, BR-015; AC-004, AC-005, AC-010.
- **Зависимости:** A-003, A-007.
- **Файлы и владение:** **[NEW REPO]** `deploy/ansible.cfg`,
  `deploy/inventory.example.ini`, `deploy/.gitignore`, `deploy/playbook-test.yml`,
  `deploy/playbook-prod.yml`, `deploy/roles/vless_agent/**`,
  `deploy/group_vars/*.example.yml`, `deploy/tests/`.
- **RED:** Molecule/unittest-style deploy tests требуют TLS certificate
  verification, backend-only source allowlist, отсутствия plaintext host
  listener, unique node token lookup, image digest и full deploy revision.
  Отдельные tests требуют fail-closed при пересечении `172.31.255.0/28` с
  host routes/interfaces или другими Docker networks, при drift уже созданной
  management network, неверных static IP, публикации agent port или
  дополнительной agent network.
- **Минимальное production-изменение:** idempotent Ansible role по образцу
  sibling operational layout, но без копирования его inventory/env; rolling
  replacement сохраняет snapshot. До старта выполняется network preflight;
  после старта runtime inspection подтверждает точную topology и прямой
  аутентифицированный HTTP health с хоста к `172.31.255.3`. Только затем
  устанавливается/reloads nginx vhost и проверяется внешний аутентифицированный
  HTTPS health. Plaintext разрешён только для этого host-nginx upstream внутри
  Compose-owned `internal` bridge и не является удалённо достижимым
  private-address endpoint.
- **Документация:** test deploy, prod deploy, staged token rotation, firewall,
  snapshot backup/downgrade compatibility, rollback и первый вариант
  `docs/COMPATIBILITY.md`; все agent deploy/compatibility docs завершаются в
  feature branch до A-010.
- **Проверка:** `uv run pytest deploy/tests -q && ansible-playbook -i deploy/inventory.example.ini deploy/playbook-test.yml --syntax-check -e deploy_revision=0000000000000000000000000000000000000000`.
- **Готово, когда:** syntax/security tests зелёные и dry-run не содержит raw
  secret/IP, plaintext API или floating revision.

### A-009 — Добавить безопасную наблюдаемость и recovery runbook

- **Результат:** metrics/logs отражают readiness, revision drift, apply latency,
  overflow, auth/TLS/Xray failures без UUID/token/full payload.
- **BR/AC:** BR-006, BR-008, BR-014, BR-016; AC-004, AC-011.
- **Зависимости:** A-006, A-008.
- **Файлы и владение:** **[NEW REPO]** `src/observability/`,
  `tests/unit/test_observability.py`, `docs/RUNBOOK.md`, `docs/SECURITY.md`,
  Compose logging settings.
- **RED:** captured metrics/log tests запрещают UUID, Authorization, snapshot
  body/private key и требуют stable counters для conflict/overflow/drift.
- **Минимальное production-изменение:** bounded structured logging/metrics и
  health reason codes; alert delivery остаётся операторской конфигурацией.
- **Документация:** восстановление после crash/drift, изоляция публичного
  listener отставшей ноды и безопасная диагностика.
- **Проверка:** `uv run pytest tests/unit/test_observability.py -q`.
- **Готово, когда:** failure fixtures создают только маскированные события и
  runbook однозначно восстанавливает exact snapshot.

### A-010 — Завершить direct-bridge bootstrap и final release evidence

- **Результат:** agent PR имеет зелёный full suite и два последовательно
  проверенных immutable SHA: direct-bridge bootstrap и final head. Final head
  проверен на выделенном тестовом сервере вместе с rollback на bootstrap и
  forward redeploy до начала backend mutation integration.
- **BR/AC:** BR-006, BR-007, BR-008, BR-013, BR-014; AC-003, AC-004, AC-005.
- **Зависимости:** A-001..A-009.
- **Файлы и владение:** **[NEW REPO]** Compose/network topology, Ansible
  preflight/runtime inspection, их tests, CI workflow и финальная проверка
  `docs/DEPLOY.md`, `docs/COMPATIBILITY.md`, `docs/RUNBOOK.md`;
  локально gitignored `deploy/inventory.test.ini` после получения
  адреса/SSH-доступа. Exact SHA evidence хранится во внешнем PR/release report,
  а не в tracked файле, который изменил бы собственный SHA.
- **RED:** topology/deploy regression tests запрещают прежний loopback upstream
  и требуют exact internal bridge/static IP/no agent ports; test-deploy evidence
  фиксирует наблюдавшуюся недоступность loopback topology на Docker 29.6.
  Preflight tests отклоняют host/Docker overlap и drift. Runtime ordering test
  требует inspection и direct authenticated health до nginx.
  Release-evidence check не принимает branch name/floating image,
  непроверенный SHA, loopback SHA как rollback target, отсутствующий consumer
  fixture или незаполненный test smoke/rollback/forward redeploy.
- **Минимальное production-изменение:**
  1. реализовать direct bridge и создать bootstrap SHA; явно отключить rollback
     на прежний loopback SHA, затем выполнить review, CI и test deploy именно
     bootstrap SHA;
  2. tracked-изменением compatibility matrix объявить проверенный bootstrap SHA
     rollback-compatible, создать final SHA, повторить review, CI и test deploy,
     выполнить controlled rollback на bootstrap и forward redeploy exact final
     SHA.
- **Документация:** оба exact SHA, Xray digest, причина несовместимости
  loopback SHA на Docker 29.6, network preflight/runtime inspection, test node
  direct+external health, empty+non-empty apply, stale/conflict, restart restore,
  rollback на bootstrap и forward redeploy final.
- **Проверка:** для каждого из bootstrap и final:
  `uv run pytest -q && uv run pytest deploy/tests -q && docker compose -f docker-compose.yml config --quiet && ansible-playbook -i deploy/inventory.test.ini deploy/playbook-test.yml --syntax-check -e deploy_revision="$(git rev-parse HEAD)"`, затем review/CI точного SHA и controlled test-node smoke. Для final дополнительно выполняются rollback exact bootstrap SHA, проверка authenticated health/snapshot restore и forward redeploy exact final SHA с повторной health/snapshot проверкой.
- **Готово, когда:** agent PR оставлен открытым с финальным
  `VERDICT: approved` для exact final head, bootstrap и final имеют отдельные
  зелёные review/CI/test-deploy evidence, test node принимает contract v1 через
  внешний HTTPS endpoint, а rollback на bootstrap и forward redeploy final
  успешны. Backend-плану передаётся только final SHA вместе с bootstrap rollback
  evidence. Любое последующее tracked изменение agent, включая compatibility,
  docs/CI, лишает прежнее evidence статуса evidence текущего head и требует
  нового полного review и test deploy нового head до R-004/R-005; историческое
  exact bootstrap evidence сохраняется только для проверки rollback target.

### Партии delivery unit A

| Партия | Пункты | Порядок / параллельность |
|---|---|---|
| A-B1-bootstrap | A-001 | Root-owned external repo bootstrap; не передаётся child implementer-у, затем отдельная проверка repo/branch |
| A-B1-contract | A-002 | Отдельный implementer/reviewer после root bootstrap |
| A-B2-auth | A-003 | Отдельный implementer и отдельный reviewer; может идти параллельно A-B2-xray после A-002 |
| A-B2-xray | A-004 | Отдельный implementer и отдельный reviewer; может идти параллельно A-B2-auth после A-002 |
| A-B3 | A-005, A-006 | Последовательно |
| A-B4 | A-007, A-008 | Последовательно |
| A-B5 | A-009, A-010 | Последовательно |

После A-B5 обязательны интеграционное review agent PR и test deploy. Backend
пункты, отправляющие mutation `PUT /snapshot`, до этого gate не начинаются.

## Delivery unit B — `my-mtproto-backend`: платежное основание

Эта фаза готовит rollback-safe SQLite schema и durable payment pipeline. Она
содержит девять атомарных пунктов. Ветка backend уже существует как
`codex/vless-vpn-sales`; изменения утверждённых документов сохраняются.

### B-001 — Реализовать read-only migration preflight

- **Результат:** management command блокирует release при 0/N active Products,
  duplicate non-empty payment identities, orphan relations или неподготовленном
  SQLite backup/space condition.
- **BR/AC:** BR-012, BR-018; AC-008, AC-013.
- **Зависимости:** C-002; не зависит от agent runtime.
- **Файлы и владение:** backend
  `src/apps/payments/management/commands/vless_migration_preflight.py`, явные
  package exports, `src/apps/payments/tests/test_management/`.
- **RED:** production-like SQLite fixtures для 0/1/N active Products,
  blank/duplicate charge IDs, gifts, orphan rows и safe PK/code/status output.
- **Минимальное production-изменение:** read-only selectors и command; никаких
  исправлений данных и вывода коммерческих/provider данных.
- **Документация:** preflight stop conditions и ручное разрешение неоднозначных
  данных.
- **Проверка:** `make test ARGS="apps.payments.tests.test_management.test_vless_migration_preflight"`.
- **Готово, когда:** только валидный production-like fixture даёт exit 0, а
  каждый риск даёт non-zero без mutation БД.

### B-002 — Добавить rollback-safe expand поля Product/Payment

- **Результат:** nullable conditional-unique `Product.code`, nullable
  `Payment.product`, общая identity uniqueness для новых непустых payments и
  deterministic backfill `mtproto_30d` без изменения `Payment.key`.
- **BR/AC:** BR-001, BR-003, BR-012, BR-017, BR-018; AC-008, AC-012, AC-013.
- **Зависимости:** B-001.
- **Файлы и владение:** backend `src/apps/payments/models.py`, `enums.py`,
  `selectors.py`, expand/data migrations, factories/admin, migration tests.
- **RED:** `MigrationExecutor` tests на one-product backfill, ambiguous inactive
  rows, duplicate guard, legacy old-writer insert после forward migration и
  lookup только по stable code.
- **Минимальное production-изменение:** только nullable fields/constraints;
  legacy null reads сохраняются, NOT NULL/contract migration вне MVP.
- **Документация:** `docs/apps/PAYMENTS.md`, `docs/MODELS.md`, rollback window.
- **Проверка:** `make test ARGS="apps.payments.tests.test_migrations apps.payments.tests.test_selectors"`.
- **Готово, когда:** expand migration проходит копию SQLite, старый writer после
  неё всё ещё создаёт legacy Payment, `Payment.key` contract не изменён.

### B-003 — Добавить PaymentIntent и PaymentReceipt

- **Результат:** durable immutable intent/receipt state machines с уникальным
  payload/identity, TTL, lease/retry и nullable applied Payment relation.
- **BR/AC:** BR-003, BR-005, BR-006, BR-012, BR-013, BR-014, BR-018; AC-002,
  AC-004, AC-005, AC-008, AC-013.
- **Зависимости:** B-002.
- **Файлы и владение:** backend `src/apps/payments/models.py`, `enums.py`,
  `exceptions.py`, `selectors.py`, migrations, `services/dtos/`, tests/factories.
- **RED:** model/service tests на 256-bit payload, CREATED/APPROVED/PAID,
  approved-after-TTL acceptance, immutable amount/currency/provider,
  duplicate/mismatched charge and stale lease.
- **Минимальное production-изменение:** модели и selectors; API и fulfillment
  ещё не подключены.
- **Документация:** model docstrings и `docs/apps/PAYMENTS.md` state tables.
- **Проверка:** `make test ARGS="apps.payments.tests.test_payment_intent apps.payments.tests.test_payment_receipt"`.
- **Готово, когда:** constraints/state transitions отклоняют конфликт identity,
  но matching retry идемпотентен.

### B-004 — Добавить модели VPN domain и admin validation

- **Результат:** `VPNAccess`, `VPNPurchase`, `VPNNode`,
  `VPNAccessNodeApply` отражают desired/published revisions, stable token,
  purchases, health и refund audit.
- **BR/AC:** BR-001, BR-002, BR-007, BR-009, BR-010, BR-011, BR-016, BR-017;
  AC-003, AC-006, AC-007, AC-009, AC-011, AC-012.
- **Зависимости:** B-002; может выполняться параллельно B-003, файлы не
  пересекаются кроме planned migration dependency.
- **Файлы и владение:** backend новый `src/apps/vpn/` с `models.py`, `enums.py`,
  `exceptions.py`, `selectors.py`, `admin.py`, `apps.py`, migrations, tests и
  явными `__init__.py`; `src/config/settings/base.py` registration.
- **RED:** factories/model tests на uniqueness, BaseDjangoModel, stable token,
  state invariants, IPv4/IPv6/DNS, X25519 public key, even hex short-id ≤16,
  SNI, port, fingerprint/flow и запрет private REALITY data.
- **Минимальное production-изменение:** schema/admin validation без network
  calls; agent secret хранится только как lookup key.
- **Документация:** `docs/apps/VPN.md`, ERD в `docs/MODELS.md`.
- **Проверка:** `make test ARGS="apps.vpn.tests.test_models apps.vpn.tests.test_admin"`.
- **Готово, когда:** все доменные constraints/validation зелёные, admin маскирует
  subscription token и не принимает private key/target.

### B-005 — Реализовать availability, intent и pre-checkout services

- **Результат:** invoice и pre-checkout проверяют flag, `vless_30d`, обе цены,
  READY/capacity-compatible node и exact immutable intent fields.
- **BR/AC:** BR-003, BR-013, BR-015, BR-018; AC-001, AC-002, AC-005, AC-010,
  AC-013.
- **Зависимости:** B-003, B-004.
- **Файлы и владение:** backend `src/apps/payments/services/payment_intents.py`,
  DTO/contracts/factories; `src/apps/vpn/services/check_sale_availability.py`,
  selectors/exceptions/settings; focused tests.
- **RED:** tests flag off, missing/partial prices, no READY node, prospective
  overflow/incompatible node, TTL, mismatch, idempotent matching pre-checkout и
  state change between invoice/pre-checkout.
- **Минимальное production-изменение:** frozen services with injected
  availability contract and module-level factories; no views yet.
- **Документация:** service docstrings and `docs/BUSINESS.md` configuration note.
- **Проверка:** `make test ARGS="apps.payments.tests.test_payment_intent_services apps.vpn.tests.test_sale_availability"`.
- **Готово, когда:** invoice/pre-checkout допускаются только при полном наборе
  условий, а approved intent не истекает автоматически.

### B-006 — Принимать successful payment в durable receipt

- **Результат:** matching Telegram payment быстро и идемпотентно создаёт receipt
  независимо от flag/node state после approved pre-checkout.
- **BR/AC:** BR-005, BR-006, BR-012, BR-014, BR-015; AC-002, AC-004, AC-008,
  AC-010.
- **Зависимости:** B-003, B-005.
- **Файлы и владение:** backend
  `src/apps/payments/services/accept_payment_receipt.py`, DTO, selectors,
  exceptions/factory and focused tests.
- **RED:** duplicate exact delivery, same charge/different immutable data,
  approved TTL elapsed, flag/node down after approval, unknown/unapproved intent,
  RUB/XTR amount and charge IDs.
- **Минимальное production-изменение:** one short atomic service that moves
  intent to PAID and inserts/returns receipt; он не импортирует/не вызывает vpn
  task. Immediate enqueue может быть injected callback из B-009, но durable
  receipt всегда остаётся выбираемым vpn-owned recovery.
- **Документация:** identity conflict/alert semantics in payment docs.
- **Проверка:** `make test ARGS="apps.payments.tests.test_accept_payment_receipt_service"`.
- **Готово, когда:** exact replay returns same receipt, conflict never applies a
  period, and broker failure leaves selectable RECEIVED state.

### B-007 — Реализовать single-owner ApplyPaymentReceiptService

- **Результат:** payment app alone claims leased receipt, creates one Payment,
  invokes an injected fulfillment protocol and commits APPLIED atomically.
- **BR/AC:** BR-002, BR-006, BR-009, BR-012, BR-014, BR-017; AC-004, AC-006,
  AC-007, AC-008, AC-012.
- **Зависимости:** B-003, B-006.
- **Файлы и владение:** backend
  `src/apps/payments/services/apply_payment_receipt.py`, protocol/DTO/factory,
  selectors, tests; payments must not import `apps.vpn`.
- **RED:** mock fulfillment tests for duplicate lease, stale lease, two charges
  in order, SQLite lock retry, rollback of Payment+fulfillment+receipt together
  and no `select_for_update()` assumption.
- **Минимальное production-изменение:** frozen orchestrator with injected
  `VPNPaymentFulfillment`; consuming task/composite wiring остаются вне payments
  и появляются только после concrete fulfillment в B-008/B-009.
- **Документация:** owner/import direction and transaction boundary in
  `docs/ARCHITECTURE.md`.
- **Проверка:** `make test ARGS="apps.payments.tests.test_apply_payment_receipt_service"`.
- **Готово, когда:** only current lease may complete, rollback is all-or-nothing,
  and import-graph test proves `payments -> vpn` absent.

### B-008 — Реализовать VPN fulfillment и vpn-owned composition root

- **Результат:** first/renewal purchase creates or extends one VPNAccess by
  `max(expired_at, accepted_at)+30d`, creates unique VPNPurchase and provides a
  vpn-owned factory that injects concrete fulfillment into B-007.
- **BR/AC:** BR-001, BR-002, BR-006, BR-009, BR-010, BR-012, BR-014, BR-017;
  AC-004, AC-006, AC-007, AC-008, AC-012.
- **Зависимости:** B-004, B-007.
- **Файлы и владение:** backend `src/apps/vpn/services/fulfill_purchase.py`,
  `src/apps/vpn/factories/payment_receipts.py`, selectors/DTO/tests; payment app
  не импортирует vpn и не содержит concrete factory/task.
- **RED:** first purchase, active/expired renewal, two sequential receipts,
  same receipt retry, stable 256-bit token/UUID, no MTProto/free/referral/gift
  mutation, rollback on VPNPurchase failure и import-graph direction.
- **Минимальное production-изменение:** frozen fulfillment service и vpn-owned
  composite factory; after-commit delivery scheduler передаётся как injected
  contract и остаётся recoverable periodic reconcile даже при enqueue failure.
- **Документация:** factory/import graph, transaction boundary и paid-period
  formula.
- **Проверка:** `make test ARGS="apps.vpn.tests.test_fulfill_purchase_service apps.vpn.tests.test_payment_factory"`.
- **Готово, когда:** exact duplicate never adds time, different receipts add
  exactly 30 days in order, and payments package has no vpn implementation
  import.

### B-009 — Обеспечить vpn-owned singleton task, flock и Beat recovery

- **Результат:** one dedicated worker invokes B-008 composition root with
  concurrency/prefetch one and shared host `flock`; vpn-owned Beat recovery
  selects RECEIVED/RETRY/stale PROCESSING receipts through payments selectors.
- **BR/AC:** BR-006, BR-009, BR-012, BR-014; AC-004, AC-006, AC-007, AC-008.
- **Зависимости:** B-007, B-008.
- **Файлы и владение:** backend `src/apps/vpn/tasks/payment_receipts.py`,
  `src/apps/vpn/factories/payment_receipts.py`, vpn lock adapter,
  `src/config/settings/celery.py`, `docker-compose.yml`, deploy template/role and
  vpn task/settings/Compose tests; `src/apps/payments/tasks.py` не импортирует
  vpn и не является consumer composition root.
- **RED:** routing/default-worker isolation, concurrency/prefetch, two-process
  shared-file lock, readiness-with-lock, lost enqueue, stale lease, jitter retry,
  duplicate fulfillment and import-graph tests.
- **Минимальное production-изменение:** thin vpn tasks call the vpn factory;
  singleton Compose service mounts existing `./data`, default worker has
  explicit non-fulfillment queues and worker holds lock for receipt transaction.
- **Документация:** `docs/ARCHITECTURE.md`, `docs/DEPLOY.md`, stop-old/start-new
  rollout, task ownership and SQLite lock recovery.
- **Проверка:** `make test ARGS="apps.vpn.tests.test_payment_tasks apps.vpn.tests.test_single_writer apps.payments.tests.test_import_graph" && docker compose -f docker-compose.yml config --quiet`.
- **Готово, когда:** concrete fulfillment exists before runnable task, duplicate
  worker cannot mutate, broker loss is recovered and each receipt changes paid
  period at most once without payments→vpn import.

### Партии payment foundation

| Партия | Пункты | Порядок / параллельность |
|---|---|---|
| B-P1 | B-001, B-002 | Последовательно |
| B-P2-payments | B-003 | Отдельный implementer/reviewer; может идти параллельно B-P2-vpn после B-002 |
| B-P2-vpn | B-004 | Отдельный implementer/reviewer; может идти параллельно B-P2-payments после B-002 |
| B-P3 | B-005, B-006 | Последовательно |
| B-P4 | B-007, B-008 | Последовательно |
| B-P5 | B-009 | Отдельная партия и reviewer после concrete B-008 |

## Delivery unit B — agent integration, VPN lifecycle и Telegram UX

Эта фаза содержит девять атомарных пунктов. B-010 начинает backend agent
integration и поэтому имеет жёсткую зависимость от A-010: reviewed agent должен
быть успешно test-deployed.

### B-010 — Реализовать HTTPS transport к contract v1

- **Результат:** backend безопасно читает health/snapshot и отправляет exact
  snapshot только совместимому agent с per-node secret lookup.
- **BR/AC:** BR-006, BR-007, BR-008, BR-013, BR-014; AC-003, AC-004, AC-005.
- **Зависимости:** A-010, B-004, C-001.
- **Файлы и владение:** backend `src/apps/vpn/infra/agent_transport.py`, DTO,
  protocols, exceptions, factory, settings and tests mocked through `responses`.
- **RED:** verified HTTPS only, per-node token isolation, timeout/TLS/auth,
  contract mismatch `426`, stale/conflict/overflow mapping, response redaction
  and exact consumer fixtures from C-001.
- **Минимальное production-изменение:** frozen infra service with injected
  session/config/secret resolver; no plaintext fallback and no raw token logs.
- **Документация:** `docs/apps/VPN.md` transport and rotation contract.
- **Проверка:** `make test ARGS="apps.vpn.tests.test_agent_transport apps.vpn.tests.test_agent_contract"`.
- **Готово, когда:** consumer tests pass against A-010 SHA fixtures and
  unsupported agents never receive mutation calls.

### B-011 — Формировать canonical exact snapshots и capacity forecast

- **Результат:** deterministic per-node snapshot includes only active,
  unexpired, non-disabled desired credentials and predicts bytes/entries before
  sale.
- **BR/AC:** BR-007, BR-008, BR-013, BR-014, BR-016; AC-003, AC-004, AC-005,
  AC-011.
- **Зависимости:** A-010, B-004, B-010, C-001; выполняется после transport
  contract, не параллельно B-010.
- **Файлы и владение:** backend `src/apps/vpn/services/build_snapshot.py`, DTO,
  selectors/factory, tests and shared canonical fixtures.
- **RED:** order/hash, add/renew/reissue/expire/refund exact sets, capacity at
  boundary, no partial/chunked mutation and no published/secret data in payload.
- **Минимальное production-изменение:** pure frozen builder and selectors; no
  HTTP call.
- **Документация:** snapshot membership and capacity rules in
  `docs/apps/VPN.md`.
- **Проверка:** `make test ARGS="apps.vpn.tests.test_build_snapshot_service"`.
- **Готово, когда:** byte-identical fixture matches agent hash and every removal
  is represented by absence from the next exact snapshot.

### B-012 — Реализовать health, delivery и periodic reconcile

- **Результат:** per-node revisions advance monotonically, full sync makes node
  READY only after exact revision/hash match, failures become observable states.
- **BR/AC:** BR-006, BR-007, BR-008, BR-013, BR-014; AC-003, AC-004, AC-005.
- **Зависимости:** B-009, B-010, B-011.
- **Файлы и владение:** backend `src/apps/vpn/services/reconcile.py`,
  `health_check.py`, selectors/factories, `tasks/reconcile.py`, Celery schedule,
  tests; package exports обновляются в этой последовательной партии.
- **RED:** lost task, agent restart recovery-ready, one-node failure, all-node
  failure, stale/conflict, incompatible/overflow, bounded retry+jitter, 5-minute
  health and hourly full reconcile.
- **Минимальное production-изменение:** thin tasks inject transport/builder;
  conditional revision/hash updates and deduplicated safe alerts.
- **Документация:** reconcile state machine and failure runbook.
- **Проверка:** `make test ARGS="apps.vpn.tests.test_reconcile_service apps.vpn.tests.test_health_check_service apps.vpn.tests.test_tasks"`.
- **Готово, когда:** health alone cannot mark READY, periodic full sync repairs
  lost work, and one bad node does not block another.

### B-013 — Публиковать readiness и доставлять URL at-least-once

- **Результат:** desired revision becomes published only after one eligible node
  confirms exact apply; durable recovery sends the stable URL separately.
- **BR/AC:** BR-005, BR-007, BR-008, BR-014; AC-002, AC-003, AC-004.
- **Зависимости:** B-008, B-012.
- **Файлы и владение:** backend `src/apps/vpn/services/publish_readiness.py`,
  `send_ready_notification.py`, tasks/selectors/factories, tests patching
  `apps.core.bot.TelegramBot`.
- **RED:** no node/no notification, first matching node publishes, wrong/old
  revision ignored, lost enqueue recovered by Beat, Telegram failure retries,
  marker advances only after send.
- **Минимальное production-изменение:** conditional publish service and
  at-least-once notification task; raw URL/token excluded from logs.
- **Документация:** PREPARING→READY and duplicate-notification tradeoff.
- **Проверка:** `make test ARGS="apps.vpn.tests.test_publish_readiness_service apps.vpn.tests.test_ready_notification"`.
- **Готово, когда:** payment ack precedes URL, no URL leaks before readiness and
  broker/Telegram failure cannot permanently lose delivery.

### B-014 — Реализовать subscription generator, endpoint и throttle

- **Результат:** stable public URL returns ordered Base64 VLESS+REALITY links
  only for eligible applied nodes, with safe empty/not-ready/unknown semantics.
- **BR/AC:** BR-007, BR-008, BR-010, BR-011, BR-015, BR-016; AC-003, AC-009,
  AC-010, AC-011.
- **Зависимости:** B-004, B-011, B-013.
- **Файлы и владение:** backend `src/apps/vpn/services/build_subscription.py`,
  public DRF view/serializer/urls, Redis throttle/redaction middleware, Nginx
  location/config and tests.
- **RED:** Base64/newlines, percent encoding, IPv6 brackets, node order/filter,
  old published UUID during reissue, `503+Retry-After`, empty expired/disabled,
  unknown `404`, no-store/nosniff, trusted-IP shared `429` and access-log token
  redaction.
- **Минимальное production-изменение:** pure generator, read-only endpoint and
  token-hash throttle; GET performs no provision/DB writes.
- **Документация:** exact public contract in `docs/CONTRACTS.md`, Nginx trusted
  proxy/logging configuration.
- **Проверка:** `make test ARGS="apps.vpn.tests.test_subscription_service apps.vpn.tests.test_subscription_view apps.vpn.tests.test_subscription_throttle" && docker compose -f docker-compose.yml config --quiet`.
- **Готово, когда:** supported links import from fixtures, secrets/private
  REALITY values never appear and all response/status/header cases are exact.

### B-015 — Реализовать lifecycle: reissue, expiration и refund

- **Результат:** reissue preserves token/old published UUID until ready;
  expiration/refund remove credentials through exact reconcile, refund is
  audited/idempotent.
- **BR/AC:** BR-010, BR-011, BR-015, BR-016, BR-017; AC-009, AC-010, AC-011,
  AC-012.
- **Зависимости:** B-010, B-011, B-012, B-014.
- **Файлы и владение:** backend `src/apps/vpn/services/reissue.py`,
  `expire_accesses.py`, `deactivate_refund.py`, selectors/tasks/admin action,
  conditional-update tests.
- **RED:** stable token, old published revision until apply, concurrent reissue
  `409`, expired access empty, lost expiration enqueue repaired by reconcile,
  repeated refund no-op with actor/reason/time, no MTProto/referral/gift changes.
- **Минимальное production-изменение:** frozen services with conditional
  `state_revision`; no `select_for_update()` guarantee and no irreversible
  cleanup marker.
- **Документация:** lifecycle state table, eventual old-UUID revocation risk and
  operator isolation runbook.
- **Проверка:** `make test ARGS="apps.vpn.tests.test_reissue_service apps.vpn.tests.test_expiration_service apps.vpn.tests.test_refund_service"`.
- **Готово, когда:** lifecycle tests prove stable URL/no access gap and exact
  snapshots eventually remove expired/refunded UUIDs.

### B-016 — Открыть bot-auth VPN API

- **Результат:** intent, pre-checkout, payment receipt, status and reissue
  endpoints expose approved status/error DTO exactly; subscription remains the
  sole public exception.
- **BR/AC:** BR-003, BR-005, BR-006, BR-007, BR-013, BR-014, BR-015, BR-018;
  AC-001, AC-002, AC-003, AC-004, AC-005, AC-010, AC-013.
- **Зависимости:** B-005, B-006, B-012, B-013, B-015.
- **Файлы и владение:** backend `src/apps/vpn/api/v1/` serializers/views/urls
  and exports, `src/config/urls.py`, API tests with `Bot-Auth-Token`.
- **RED:** exact `200/202/400/404/409/503`, stable error body, auth required,
  payload/currency/amount for RUB/XTR, successful-payment bypass of flag/down,
  state DTO and URL only when READY.
- **Минимальное production-изменение:** thin DRF views invoking factories;
  internal UUID/tokens/provider payload never enter error detail.
- **Документация:** all new endpoints and examples in `docs/CONTRACTS.md`.
- **Проверка:** `make test ARGS="apps.vpn.tests.test_views"`.
- **Готово, когда:** API matrix matches architecture and existing MTProto/gift
  endpoint tests remain green.

### B-017 — Добавить отдельный VPN UX в Telegram-бот

- **Результат:** bot VPN section supports status, RUB/Stars invoice,
  pre-checkout, immediate preparing acknowledgement, later URL and reissue
  without changing MTProto flows.
- **BR/AC:** BR-001, BR-003, BR-004, BR-005, BR-007, BR-010, BR-011, BR-013,
  BR-015, BR-017, BR-018; AC-001, AC-002, AC-003, AC-005, AC-009, AC-010,
  AC-012, AC-013.
- **Зависимости:** B-016.
- **Файлы и владение:** backend repo `bot/src/domains/vpn/`,
  `bot/src/handlers/vpn.py`, router/dependencies/keyboards/messages, payment
  successful/pre-checkout routing by random payload; `bot/tests/domains/vpn/`
  and handler tests.
- **RED:** separate section, both currencies, exact intent payload passthrough,
  backend pre-checkout rejection, successful-payment routing, immediate text,
  PREPARING/READY/EXPIRED/DISABLED states, flag-hidden sale buttons and unchanged
  MTProto/gift paths.
- **Минимальное production-изменение:** typed async backend client and handlers;
  bot does not infer product from text/currency and does not create VPNAccess.
- **Документация:** bot UX/messages in `docs/BUSINESS.md` and contract mapping.
- **Проверка:** `cd bot && uv run pytest tests/domains/vpn tests/test_handlers.py -q`.
- **Готово, когда:** all VPN scenarios are green and complete existing bot suite
  has no MTProto/gift regressions.

### B-018 — Добавить observability, alerts и безопасное логирование

- **Результат:** backend exposes required receipt/readiness/node/subscription
  metrics and deduplicated alerts without secrets or personal URLs.
- **BR/AC:** BR-006, BR-008, BR-013, BR-014, BR-016; AC-004, AC-005, AC-011.
- **Зависимости:** B-008, B-009, B-011, B-012, B-013, B-014, B-015.
- **Файлы и владение:** backend `src/apps/vpn/observability.py`, safe alert
  service, logging middleware/settings, tests; Flower/Celery/Nginx docs/config.
- **RED:** stale receipt, no READY node, incompatible/overflow/drift,
  auth/TLS/reconcile/notification failure counters; captured logs reject UUID,
  token, raw URI, payload, Authorization and full snapshot.
- **Минимальное production-изменение:** structured safe fields and stable
  deduplication keys; no new external monitoring dependency.
- **Документация:** alert thresholds and operator response in
  `docs/apps/VPN.md`/`docs/DEPLOY.md`.
- **Проверка:** `make test ARGS="apps.vpn.tests.test_observability apps.core.tests.test_request_logging"`.
- **Готово, когда:** each required failure emits one actionable safe event and
  redaction regression tests are green.

### Партии backend integration

| Партия | Пункты | Порядок / параллельность |
|---|---|---|
| B-I1 | B-010, B-011 | Строго последовательно после A-010; один implementer/reviewer, transport затем builder/parity |
| B-I2 | B-012, B-013 | Последовательно |
| B-I3 | B-014, B-015 | Последовательно |
| B-I4 | B-016 | Отдельная партия/reviewer после lifecycle |
| B-I5-bot | B-017 | Отдельный implementer/reviewer; может идти параллельно B-I5-obs после B-016 |
| B-I5-obs | B-018 | Отдельный implementer/reviewer; может идти параллельно B-I5-bot после B-016 и B-015 |

## Фаза R — интеграция, документация и release gates

Фаза содержит шесть пунктов. Это ответственность главного оркестратора и
reviewers, а не разрешение дочерним implementer-ам выполнять production deploy.

### R-001 — Выполнить backend migration/rollback rehearsal

- **Результат:** expand migration измерена на production-like SQLite copy,
  backup/restore проверен, legacy rollback writer совместим.
- **BR/AC:** BR-006, BR-012, BR-014; AC-004, AC-008.
- **Зависимости:** B-001..B-018.
- **Файлы и владение:** backend test fixtures/scripts, release evidence only;
  production DB не изменяется.
- **RED:** rehearsal считается failed без preflight exit 0, timed migrate,
  integrity check, restored DB equality and old-writer insert.
- **Минимальное production-изменение:** нет.
- **Документация:** evidence в
  `docs/features/vless-vpn-sales/acceptance.md`, без данных/секретов.
- **Проверка:** `make test ARGS="apps.payments.tests.test_migrations"` плюс
  documented SQLite copy migrate/restore rehearsal.
- **Готово, когда:** evidence содержит timings/checksums/outcomes, ambiguous
  production-like data safely blocks rollout and no contract migration exists.

### R-002 — Обновить backend-документацию и read-only сверить agent docs

- **Результат:** backend contracts/models/runtime/runbooks отражены без
  дублирующих правил, а уже зафиксированные A-010 agent docs только read-only
  сверены с exact agent SHA.
- **BR/AC:** BR-001..BR-018; AC-001..AC-013.
- **Зависимости:** A-010, B-018, R-001.
- **Файлы и владение:** backend `docs/BUSINESS.md`, `docs/ARCHITECTURE.md`,
  `docs/CONTRACTS.md`, `docs/MODELS.md`, `docs/apps/PAYMENTS.md`,
  `docs/apps/VPN.md`, `docs/DEPLOY.md`, feature acceptance. **[NEW REPO]**
  `README.md` и `docs/**` в этом пункте доступны только для read-only проверки;
  backend implementer их не изменяет.
- **RED:** traceability/doc-link check fails on missing BR/AC, wrong endpoint,
  unpinned Xray, plaintext agent or non-single-writer wording.
- **Минимальное production-изменение:** нет.
- **Документация:** сам пункт является backend documentation consolidation;
  найденное расхождение agent docs возвращается agent implementer-у и запускает
  новый A-010 review+test-deploy, а не исправляется здесь.
- **Проверка:** `rg -n "BR-0|AC-0|VPN_SALES_ENABLED|vpn_payment_fulfillment|agent contract v1|Xray" docs ../my-vless-vds-instance/docs && test "$(git -C ../my-vless-vds-instance rev-parse HEAD)" = "$AGENT_A010_SHA" && test -z "$(git -C ../my-vless-vds-instance status --short)" && git diff --check`.
- **Готово, когда:** backend docs match code/tests, superseded design is not
  normative, prices/IP/secrets are absent, agent worktree/head SHA не изменены.
  Любое необходимое agent изменение инвалидирует старое A-010 evidence и
  повторяет полный agent review+test-deploy до R-004/R-005.

### R-003 — Провести полную backend+bot verification и продуктовую приёмку

- **Результат:** full suites, Compose, migration checks и acceptance scenarios
  зелёные при sales flag off.
- **BR/AC:** BR-001..BR-018; AC-001..AC-013.
- **Зависимости:** R-002.
- **Файлы и владение:** только acceptance evidence; исправления возвращаются
  исходным implementer-ам.
- **RED:** любой failed BR/AC, regression, Compose error, leaked secret or
  untraced requirement blocks publication.
- **Минимальное production-изменение:** нет.
- **Документация:** заполнить `acceptance.md` командами и результатами.
- **Проверка:** `make test && cd bot && uv run pytest -q && cd .. && docker compose -f docker-compose.yml config --quiet && git diff --check`.
- **Готово, когда:** все проверки зелёные, `VPN_SALES_ENABLED=False` default,
  product-reviewer принимает AC-001..AC-013.

### R-004 — Опубликовать два PR и финально проверить точные SHA

- **Результат:** отдельные agent/backend PR в `main` оставлены открытыми, каждый
  имеет зелёные checks и финальный review exact head SHA.
- **BR/AC:** BR-006, BR-012, BR-014, BR-015; AC-004, AC-008, AC-010.
- **Зависимости:** A-010, R-003.
- **Файлы и владение:** PR bodies/release evidence; reviewer допускается только
  `gh pr review --comment`, без push/merge/edit/close.
- **RED:** stale head SHA, agent head отличный от A-010 reviewed/test-deployed
  SHA, missing check, changed worktree during review or verdict other than exact
  `VERDICT: approved` blocks gate; новый agent commit возвращает поток в A-010.
- **Минимальное production-изменение:** нет.
- **Документация:** PR body lists scope, BR/AC, tests, migration/deploy risks and
  compatible counterpart SHA.
- **Проверка:** для каждого repo `gh pr checks <number> --watch && test "$(gh pr view <number> --json headRefOid --jq .headRefOid)" = "<reviewed-sha>"`.
- **Готово, когда:** оба PR URL, exact head SHA and approved review comments
  recorded; neither PR is merged.

### R-005 — Выполнить coordinated non-production smoke release pair

- **Результат:** reviewed agent SHA на test node и reviewed backend SHA в
  локальном/staging stack подтверждают весь delayed fulfillment lifecycle.
- **BR/AC:** BR-001..BR-018; AC-001..AC-013.
- **Зависимости:** R-004 и неизменный A-010 agent head; доступ к тестовой ноде
  передаётся вне git.
- **Файлы и владение:** в обоих репозиториях — никаких файлов и никаких
  изменений worktree. Используются уже подготовленные вне R-005 test
  inventory/env; evidence публикуется как два структурированных PR-комментария
  с одинаковым marker `VLESS-SMOKE-EVIDENCE` либо во внешнем release system, но
  не записывается в tracked/untracked файлы репозиториев.
- **RED:** smoke failed if no exact SHA/contract match, test node is not READY,
  client import/connection failed, or any
  invoice/payment/readiness/renew/reissue/recovery/refund/flag-off step differs.
- **Минимальное production-изменение:** test/staging only; production и оба
  repository worktree/HEAD не изменяются.
- **Документация:** структурированные PR-комментарии фиксируют оба reviewed SHA,
  Android/iOS versions, Xray digest, команды/результаты smoke, delayed readiness,
  node recovery и rollback rehearsal без credentials; локальные docs не
  изменяются.
- **Проверка:** до smoke сохранить для обоих repo `git rev-parse HEAD` и точный
  `git status --short --untracked-files=all`; выполнить full suites и controlled
  end-to-end smoke из уже reviewed `release-checklist.md`; опубликовать sanitized
  comments через `gh pr comment`. После smoke проверить равенство pre/post HEAD и
  status обоих repo, затем через `gh pr view <number> --json comments` найти на
  обоих PR marker, оба reviewed SHA и успешные результаты.
- **Готово, когда:** exact release pair passes contract, real Xray, import and
  connection smoke; sales flag remains off outside the controlled test; оба
  HEAD/status побайтно равны pre-smoke значениям, а evidence существует только
  во внешних structured comments/report и ссылается на reviewed SHA R-004.

### R-006 — Остановиться на пользовательских merge/deploy gates

- **Результат:** пользователь получает два открытых PR, те же reviewed
  SHA/checks и связанные `VLESS-SMOKE-EVIDENCE` comments с явной оставшейся
  release sequence; никаких production/repository mutations.
- **BR/AC:** BR-006, BR-013, BR-014, BR-015; AC-004, AC-005, AC-010.
- **Зависимости:** R-005.
- **Файлы и владение:** нет.
- **RED:** gate failed if evidence comments отсутствуют/расходятся по SHA,
  текущий PR head отличается от reviewed/smoke SHA, worktree изменился,
  merge/deploy permission inferred from feature approval, one permission reused
  for both actions, IP hardcoded or an implementer ran a production playbook.
- **Минимальное production-изменение:** отсутствует.
- **Документация:** final handoff names both PR URLs/head SHA/checks, URLs/IDs
  structured smoke comments and rollout risks; local files не меняются.
- **Проверка:** read-only audit обоих `gh pr view`/checks/comments подтверждает
  один и тот же reviewed SHA pair из R-004/R-005; local `git rev-parse HEAD` и
  `git status --short --untracked-files=all` совпадают с pre-smoke snapshots.
- **Готово, когда:** работа остановлена с открытыми PR. Merge выполняется только
  после отдельного явного разрешения; затем перед единым production release pair
  deploy снова запрашивается новое явное разрешение с обоими merge SHA. Sales
  enablement происходит лишь после agent-first deploy, backend deploy flag-off,
  минимум двух READY locations и post-deploy smoke.

### Партии фазы R

| Партия | Пункты | Порядок / параллельность |
|---|---|---|
| R-B1 | R-001, R-002 | Последовательно |
| R-B2 | R-003 | Отдельная продуктовая приёмка |
| R-B3-agent | R-004 (agent review) | Отдельный read-only reviewer exact agent SHA; может идти параллельно R-B3-backend |
| R-B3-backend | R-004 (backend review) | Отдельный read-only reviewer exact backend SHA; может идти параллельно R-B3-agent |
| R-B4 | R-005, R-006 | Последовательно |

## Трассировка требований к пунктам

| Требование | Основные пункты |
|---|---|
| BR-001 / AC-001 | B-002, B-004, B-008, B-017 |
| BR-002 | B-004, B-008 |
| BR-003 / AC-002 | B-003, B-005, B-016, B-017 |
| BR-004 | B-017 |
| BR-005 | B-006, B-013, B-016, B-017 |
| BR-006 / AC-004 | C-001, A-004..A-010, B-003, B-006..B-013, R-003..R-005 |
| BR-007 / AC-003 | A-004, A-006, A-007, B-004, B-011, B-013, B-014 |
| BR-008 | A-005, A-006, B-011, B-013 |
| BR-009 / AC-006 / AC-007 | B-007, B-008, B-009 |
| BR-010 | B-004, B-008, B-014, B-015 |
| BR-011 / AC-009 | A-004, A-007, B-004, B-014, B-015, B-017 |
| BR-012 / AC-008 | C-001, B-001..B-003, B-006..B-009, R-001 |
| BR-013 / AC-005 | C-002, A-010, B-005, B-011, B-012, B-016, B-017 |
| BR-014 | A-004..A-010, B-006, B-008, B-011..B-013 |
| BR-015 / AC-010 | C-002, B-005, B-006, B-014..B-017, R-006 |
| BR-016 / AC-011 | A-004, A-009, B-004, B-011, B-014, B-015, B-018 |
| BR-017 / AC-012 | B-002, B-004, B-007, B-008, B-015, B-017 |
| BR-018 / AC-013 | B-001..B-003, B-005, B-016, B-017 |

## Самопроверка plan-maker

- Все BR-001..BR-018 и AC-001..AC-013 имеют минимум один RED test и однозначный
  done criterion.
- В каждой фазе не более десяти атомарных пунктов: C — 2, A — 10, payment
  foundation — 9, backend integration — 9, R — 6.
- В каждой implementer-партии не более двух пунктов; параллельность отмечена
  только для непересекающихся apps/repositories без незавершённой зависимости.
- Contract checkpoint предшествует обеим delivery units; agent реализуется,
  ревьюится и test-deploy-ится до backend `PUT /snapshot` integration.
- План включает TDD, rollback-safe expand migrations/preflight, SQLite
  single-writer queue+shared `flock`, PaymentIntent/PaymentReceipt, exact
  snapshots, pinned Xray, HTTPS/per-node auth, reconcile/readiness/subscription,
  bot/lifecycle/observability/docs и release gates.
- Production deploy не является действием implementer-а. Merge и deploy требуют
  двух отдельных явных разрешений пользователя; feature approval их не даёт.
