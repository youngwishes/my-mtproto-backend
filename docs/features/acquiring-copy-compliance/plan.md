# Acquiring Copy Compliance Implementation Plan

> **For agentic workers:** выполнить ACC-001 и ACC-002 одним последовательным
> TDD-batch. Один `plan-implementer` владеет обоими пунктами; после него отдельный
> `code-reviewer` проверяет batch read-only. Commit, push, PR, финальный PR review,
> merge и deploy остаются у главного оркестратора.

- **Status:** approved
- **Scope revision:** 2 (immutable)
- **Route:** small local feature. Главный оркестратор зафиксировал, что
  архитектурное изменение не требуется: меняются только существующие
  пользовательские строки и данные одного существующего шаблона через новую
  forward data migration; API, модели и взаимодействия компонентов неизменны.

**Goal:** Убрать из FAQ и broadcast запрещённый контекст, направить все
пользовательские обращения за помощью на `@mtprotokeys_support`, открыть его
точный URL кнопкой поддержки и обновить существующий DB-шаблон
`sorry_server_error`, сохранив `@mtproto_keys` в новостных приглашениях.

**Approach:** Сначала тестами зафиксировать точный FAQ, URL, support contact,
нейтральный broadcast и неизменные новостные приглашения, затем сделать только
локальные замены строк. Отдельным RED→GREEN циклом добавить migration-test и
новую migration после `notifications.0011`, которая меняет только support
username в тексте `sorry_server_error`; исторические migrations не
переписываются.

**Tech stack:** Python 3.13, aiogram 3, pytest/pytest-asyncio, Django 6
`TestCase`/`TransactionTestCase`, Django migrations, Markdown, Docker Compose.

## Global Constraints

- Единственный источник обязательного поведения — approved
  `docs/features/acquiring-copy-compliance/business.md`, `scope_revision: 2`,
  BR-001–BR-006 и AC-001–AC-005.
- Точный FAQ-ответ:
  `Прокси помогает Telegram работать стабильнее и уменьшает потери при плохом интернете, защищает трафик. Максимальная скорость зависит от твоего интернета`.
  Разрешено сохранить существующий подходящий emoji/HTML, не меняющий смысл.
- Support username и URL посимвольно равны `@mtprotokeys_support` и
  `https://t.me/mtprotokeys_support`; сетевых запросов для их проверки нет.
- `@mtproto_keys` остаётся только в пользовательских приглашениях подписаться на
  новостной канал: в `KEY_GENERATED_TEXT`, `send_free_link_to_user_task` и
  `NotificationTemplate(slug="invite_to_channel")`.
- Слова VPN, MTProxy и MTProto сами по себе не запрещены. Не менять тарифы, API,
  модели, поведение продукта или содержание внешнего Telegram-канала.
- Не менять `README.md`, `bot/README.md`, внутренние/исторические документы,
  historical migrations (включая `0002_seed_templates.py`), technical
  DB/ORM-locking copy, `docs/BUSINESS.md`, `docs/ARCHITECTURE.md`,
  `docs/CONTRACTS.md`, `docs/MODELS.md`, `docs/apps/` и `apps/music/`.
- Никаких рефакторингов, новых abstractions, settings, dependencies или
  availability checks. После каждого GREEN сверять diff с разрешёнными файлами.

## File and Dependency Map

- Bot copy and handlers: `bot/src/messages.py`, `bot/src/exceptions.py`,
  `bot/src/handlers/payments.py`; regression tests расширяются в существующем
  `bot/tests/test_handlers.py`.
- Backend copy: `src/apps/notifications/services/broadcast_proxy_links_service.py`,
  `src/apps/users/exceptions.py`, `src/apps/vds/exceptions.py`; тесты —
  существующий broadcast service test и два небольших app-local exception tests.
- Persisted template: новая
  `src/apps/notifications/migrations/0012_update_sorry_server_error_support.py`
  после текущей leaf migration `0011_seed_crypto_purchase_templates.py`; новый
  migration-test следует паттерну `test_crypto_purchase_templates_migration.py`.
- Feature artifacts: approved `business.md` и этот `plan.md` implementer не
  меняет; `acceptance.md` создаёт product reviewer после batch review.

```text
ACC-B1 (one implementer, sequential):
ACC-001 -> ACC-002 -> read-only batch review -> product acceptance
        -> root integration verification -> commit/push/PR -> final PR review
```

Параллельной реализации нет: ACC-002 зависит от GREEN ACC-001 и оба пункта
входят в один пользовательский copy contract.

---

### ACC-001 — Привести статические пользовательские тексты к approved copy

**Result:** FAQ содержит точный approved ответ; broadcast больше не содержит
контекста про блокировки/обход ограничений; кнопка поддержки, bot fallbacks и
bot/backend domain exceptions указывают новый support contact; новостные
приглашения по-прежнему содержат `@mtproto_keys`.

**Traceability:** BR-001, BR-002, BR-003, BR-004, BR-006; AC-001, AC-002,
AC-003, AC-005.

**Dependencies:** approved `business.md`, `scope_revision: 2`; заключение
главного оркестратора об отсутствии архитектурного изменения; implementation
dependencies отсутствуют.

**Files and ownership:**

- Modify/Test: `bot/tests/test_handlers.py` — только assertions для точного FAQ,
  support URL/contact, двух существующих payment failure paths, bot exception и
  сохранённого news-channel mention.
- Modify: `bot/src/messages.py` — только `SUPPORT_URL`, FAQ-ответ и FAQ support
  footer; `KEY_GENERATED_TEXT` news invitation не менять.
- Modify: `bot/src/exceptions.py` — только support username в docstring
  `VPNSubscriptionDoesNotExist`.
- Modify: `bot/src/handlers/payments.py` — только support username в двух
  существующих exception fallbacks; control flow не менять.
- Modify/Test:
  `src/apps/notifications/tests/test_broadcast_proxy_links_service.py` и
  `src/apps/notifications/services/broadcast_proxy_links_service.py` — только
  user broadcast text assertions и удаление двух предложений с запрещённым
  контекстом; выдачу трёх дней, выбор получателей, отправку и error flow не
  менять.
- Create/Test: `src/apps/users/tests/test_exceptions.py`; modify:
  `src/apps/users/exceptions.py` — только exact support-contact assertion и
  username в `AlreadyUsedFree`.
- Create/Test: `src/apps/vds/tests/test_exceptions.py`; modify:
  `src/apps/vds/exceptions.py` — только exact support-contact assertions и
  username в `KeyDoesNotExist`/`KeysLimitReached`.

**RED test:**

- [ ] В `bot/tests/test_handlers.py` усилить существующие tests без создания
  общего source scanner:
  - `test_info_answers_callback` проверяет наличие точной approved FAQ-строки и
    отсутствие в показанном FAQ фраз `обходит ограничения` и `блокировок`;
  - `test_mtproxy_menu_links_to_site_and_support` проверяет
    `SUPPORT_URL == "https://t.me/mtprotokeys_support"` и этот URL в кнопке;
  - `test_vpn_subscription_without_subscription_keeps_menu_and_raises_error`
    ожидает `@mtprotokeys_support` и отсутствие старого username;
  - `test_successful_payment_warns_user_on_failure` ожидает новый username;
  - новый test вызывает существующий gift-certificate activation fallback при
    `activation_error` и ожидает новый username;
  - отдельный assertion подтверждает `@mtproto_keys` в `KEY_GENERATED_TEXT` как
    news-channel invitation.
- [ ] В broadcast service test проверить фактически переданный user `text`:
  фраз `из-за блокировок` и `обойти ограничения` нет, а существующие стабильная
  работа, трёхдневная компенсация и expiry остаются.
- [ ] В двух новых app-local `test_exceptions.py` создать соответствующие
  исключения и проверить, что user-facing `message` содержит
  `@mtprotokeys_support`, не содержит `@mtproto_keys`, а остальной тип/контракт
  исключений не меняется.
- [ ] Запустить RED до production edits:

  ```bash
  (cd bot && uv run pytest tests/test_handlers.py -k "info_answers_callback or mtproxy_menu_links_to_site_and_support or vpn_subscription_without_subscription or successful_payment_warns_user_on_failure or gift_certificate_activation" -q)
  make test ARGS="apps.notifications.tests.test_broadcast_proxy_links_service apps.users.tests.test_exceptions apps.vds.tests.test_exceptions"
  ```

  Ожидаемый RED: assertions видят старые FAQ/broadcast/support values. Падение
  импорта из-за ещё не созданного production symbol или сетевой ошибки не
  считается корректным RED.

**Minimal production change:**

- [ ] В `bot/src/messages.py` заменить URL и support footer, а только ответ под
  вопросом `Telegram тормозит или не грузит медиа?` привести к точному approved
  тексту с существующим `⚡️`; соседние FAQ ответы не менять.
- [ ] Во всех шести назначенных support call sites заменить только старый support
  username на `@mtprotokeys_support`: bot exception, два payment fallbacks,
  `AlreadyUsedFree`, `KeyDoesNotExist`, `KeysLimitReached`.
- [ ] Из user broadcast удалить только два предложения о блокировках и полном
  обходе ограничений. Оставить приветствие, утверждение о стабильной работе,
  компенсацию на три дня, expiry/link markup и всю логику сервиса неизменными.
- [ ] Повторить обе RED-команды и получить GREEN. Затем выполнить полный bot
  test file:

  ```bash
  (cd bot && uv run pytest tests/test_handlers.py -q)
  ```

**Documentation:** профильные business/architecture/contracts/models/app docs не
меняются, потому что API, модели и компоненты неизменны; implementer передаёт
точные RED/GREEN outputs для будущего `acceptance.md` и не редактирует feature
artifacts.

**Completion criterion:** targeted tests и полный `bot/tests/test_handlers.py`
GREEN; точный FAQ и URL соблюдены; все назначенные runtime support call sites
указывают новый username; news-channel strings в `KEY_GENERATED_TEXT` и
`src/apps/users/tasks.py` не изменены; diff ограничен десятью назначенными
production/test files и не содержит network calls или refactor.

---

### ACC-002 — Обновить сохранённый `sorry_server_error` новой data migration

**Result:** при переходе с `notifications.0011` на новую migration только текст
существующего `sorry_server_error` заменяет support username на
`@mtprotokeys_support`; весь остальной текст и `invite_to_channel` остаются
байт-в-байт прежними.

**Traceability:** BR-003, BR-004, BR-005, BR-006; AC-003, AC-004, AC-005.

**Dependencies:** ACC-001 GREEN; текущая notifications leaf migration
`0011_seed_crypto_purchase_templates`; существующий MigrationExecutor pattern в
`src/apps/notifications/tests/test_crypto_purchase_templates_migration.py`.

**Files and ownership:**

- Create/Test:
  `src/apps/notifications/tests/test_sorry_server_error_support_migration.py` —
  только forward migration regression from `0011` to `0012`.
- Create:
  `src/apps/notifications/migrations/0012_update_sorry_server_error_support.py`
  — только one-slug forward `RunPython`; dependency — `0011`.
- Forbidden: `src/apps/notifications/migrations/0002_seed_templates.py` и все
  иные migrations/templates/models/services.

**RED test:**

- [ ] По существующему `MigrationExecutor`/`TransactionTestCase` pattern
  мигрировать к `("notifications", "0011_seed_crypto_purchase_templates")`,
  сохранить полные исходные строки двух существующих templates, затем мигрировать
  к `("notifications", "0012_update_sorry_server_error_support")` и проверить:
  - у `sorry_server_error` прежний текст с единственной заменой
    `@mtproto_keys` → `@mtprotokeys_support`;
  - old support username в нём отсутствует;
  - `invite_to_channel.text`, включая `@mtproto_keys`, равен сохранённому
    исходному значению;
  - другие поля обоих templates не изменены.
  В `tearDown` вернуть DB к текущим leaf nodes, как в существующем migration
  test.
- [ ] Запустить до создания migration:

  ```bash
  make test ARGS="apps.notifications.tests.test_sorry_server_error_support_migration"
  ```

  Ожидаемый RED: migration target `0012_update_sorry_server_error_support` ещё
  отсутствует. Тест не выполняет network calls.

**Minimal production change:**

- [ ] Добавить migration `0012` с dependency на `0011`. Forward function через
  historical `apps.get_model("notifications", "NotificationTemplate")`
  выбирает только `slug="sorry_server_error"`, заменяет первое точное
  вхождение `@mtproto_keys` на `@mtprotokeys_support` в существующем `text` и
  сохраняет только поле `text`. Reverse operation —
  `migrations.RunPython.noop`, чтобы rollback не переписывал возможный
  последующий operator-owned text.
- [ ] Повторить migration-test до GREEN, затем выполнить объединённый targeted
  backend suite:

  ```bash
  make test ARGS="apps.notifications.tests.test_broadcast_proxy_links_service apps.notifications.tests.test_sorry_server_error_support_migration apps.users.tests.test_exceptions apps.vds.tests.test_exceptions"
  ```

**Documentation:** historical seed и профильные документы не обновлять. Передать
product reviewer точное имя migration и RED/GREEN output для фиксации AC-004 в
`docs/features/acquiring-copy-compliance/acceptance.md`.

**Completion criterion:** migration-test и объединённый targeted backend suite
GREEN; migration меняет только `sorry_server_error.text`; `invite_to_channel` и
news username неизменны; diff ACC-002 содержит только два новых файла; сетевых
проверок нет.

## Task Packet ACC-B1

- **scope_revision:** 2 (immutable).
- **Plan items:** ACC-001, затем ACC-002; один implementer, параллельная работа
  запрещена.
- **Requirements:** BR-001–BR-006; AC-001–AC-005.
- **Allowed/expected files:**
  `bot/src/messages.py`, `bot/src/exceptions.py`,
  `bot/src/handlers/payments.py`, `bot/tests/test_handlers.py`,
  `src/apps/notifications/services/broadcast_proxy_links_service.py`,
  `src/apps/notifications/tests/test_broadcast_proxy_links_service.py`,
  `src/apps/users/exceptions.py`, `src/apps/users/tests/test_exceptions.py`,
  `src/apps/vds/exceptions.py`, `src/apps/vds/tests/test_exceptions.py`,
  `src/apps/notifications/migrations/0012_update_sorry_server_error_support.py`,
  `src/apps/notifications/tests/test_sorry_server_error_support_migration.py`.
- **Forbidden adjacent work:** любые другие code/test/migration files;
  historical migrations; README; bot README; внутренние/исторические docs;
  feature artifacts; external Telegram content; technical DB/ORM-locking copy;
  tariffs/API/models/product behavior; username availability checks;
  refactor; `apps/music/`; branch/commit/push/PR/merge/deploy operations.
- **Non-goals:** все non-goals approved `business.md` применяются полностью;
  риски и найденные соседние формулировки не становятся новой работой без нового
  Scope Contract.
- **Dependencies:** approved business artifact; root no-architecture-change
  conclusion; ACC-001 GREEN до ACC-002; затем отдельный read-only batch review.
- **Budget:** два последовательных plan items, шесть существующих production
  files, два существующих tests, две новые app-local exception test modules,
  одна новая migration и один migration-test; ноль новых dependencies,
  abstractions, API/model changes или network calls.
- **Completion criterion:** оба item-level criteria выполнены, все targeted
  commands GREEN, diff состоит только из разрешённых файлов и готов к read-only
  batch review.

## Acceptance and Release Handoff

После `ACC-B1` и batch review главный оркестратор передаёт product reviewer пакет
со `scope_revision: 2`, ACC-001/ACC-002 и BR-001–BR-006/AC-001–AC-005. Reviewer
создаёт только `docs/features/acquiring-copy-compliance/acceptance.md`: фиксирует
наблюдаемое соответствие каждому AC, exact migration name и фактические команды/
результаты; не меняет code/tests/business/plan и не добавляет edge cases.

После acceptance главный оркестратор выполняет из корня:

```bash
(cd bot && uv run pytest -q)
make test
docker compose -f docker-compose.yml config --quiet
git diff --check
git status --short
```

Интеграционный критерий: bot suite и полный Django suite GREEN, Compose config и
`git diff --check` успешны, итоговый diff трассируется к scope revision 2,
historical migrations/news invitations/non-goals не затронуты, а
`acceptance.md` покрывает AC-001–AC-005 фактическими evidence.

Затем главный оркестратор, находясь в `codex/acquiring-copy-compliance`, добавляет
только feature files, создаёт commit, проверяет `gh auth status`, pushes только
feature branch и открывает PR в `main`. PR body содержит `scope_revision: 2`,
BR/AC, scope, non-goals, проверки, имя data migration и deploy impact. Он
сохраняет PR URL/number/head SHA и подтверждает, что remote PR head равен
локальному `git rev-parse HEAD`.

Новый `code-reviewer` read-only проверяет точный PR head, diff и checks и
публикует структурированный review comment с тем же SHA и
`VERDICT: approved` либо обоснованным `VERDICT: changes_requested`; обязательными
implementer fixes могут стать только подтверждённые `blocking_in_scope`. PR
остаётся открытым. Merge требует отдельного явного разрешения пользователя, а
production deploy после merge — ещё одного нового явного разрешения; этот план
не разрешает merge или deploy.
