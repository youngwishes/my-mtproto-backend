# MTProxy Telegram Stars 99 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

- **Status:** approved
- **Scope revision:** 2 (current; revision 1 is superseded and must not be used)
- **Route:** small local feature. The root agent concluded that architecture
  changes and architect review are not required: the saved `mtproto_30d` price
  is already 99, and the existing API serialization, bot invoice mapping and
  payment flows remain unchanged.

**Goal:** Пользователь видит цену MTProxy 99 ★ и получает Stars-счёт на 99 XTR
при покупке или продлении подписки и при покупке подарочного сертификата, а
текущие тестовые представления и документация отражают ту же цену.

**Architecture:** Изменение заменяет только локальные MTProxy price literals в
bot presentation layer, тестовых fixtures/helpers и документации. Invoice
клиент продолжает без преобразований переносить `stars_price` существующего
backend-товара в `LabeledPrice.amount`; модели, API logic, schema, migrations и
сохранённые данные не меняются.

**Tech Stack:** Python 3.13, Django 6/unittest, aiogram 3,
pytest/pytest-asyncio, respx/httpx, Markdown.

## Global Constraints

- Единственный источник обязательных требований — approved
  `docs/features/mtproxy-stars-99/business.md`, `scope_revision: 2`: BR-001..
  BR-003 и AC-001..AC-006. Revision 1 полностью superseded.
- Предусловие: сохранённый `mtproto_30d` уже имеет `stars_price = 99`; эта
  правка не пишет данные и не создаёт способ привести их к этому состоянию.
- Следовать TDD: сначала получить ожидаемый RED на новых или изменённых
  assertions, затем выполнить минимальные literal/fixture изменения и получить
  GREEN. Новую payment logic не добавлять.
- `Product.stars_price` сохраняет `default=80`; `docs/MODELS.md`, migration
  `0004`, остальные migrations и `test_migrations.py` не менять. Историческое
  setup-значение `stars_price=80` в migration test намеренно остаётся.
- Рублёвая цена MTProxy остаётся 99 ₽; VPN остаётся 149 ₽ / 149 ★ и не меняет
  поведение. Не менять длительность, callbacks, payloads, providers, successful
  payment flow или API contract shape.
- Разрешены только восемь implementation-файлов, перечисленных в task packet.
  Не читать, не изменять и не включать в audit `apps/music/`.
- Бюджет — два атомарных пункта у одного implementer-а в одном
  последовательном batch; без новых файлов, модулей, зависимостей, abstractions
  или refactor.
- Implementer не создаёт ветку, commit, push, PR, merge или deploy; эти gates
  остаются у главного оркестратора.

## File and Interface Map

- `bot/tests/test_handlers.py` — фиксирует exact 99 ★ в FAQ/payment screens и
  subscription/gift keyboards, а также 99 XTR в forwarded Stars invoices.
- `bot/src/messages.py` — только два MTProxy copy literals: FAQ и payment
  methods text.
- `bot/src/keyboards.py` — только статические Stars labels subscription и gift
  certificate; динамическую VPN keyboard не менять.
- `bot/tests/domains/payments/test_client.py` — `PRODUCT_JSON` представляет
  текущий MTProxy-товар с `stars_price: 99`; invoice mapping ожидает
  `LabeledPrice.amount == 99`.
- `src/apps/payments/models.py` — только явный `stars_price=99` внутри
  `ProductQuerySet.create_test_product`; field declaration с `default=80`
  остаётся дословно прежним.
- `src/apps/payments/tests/factories.py` — текущий MTProxy `ProductFactory`
  использует `stars_price = 99`; VPN tests продолжают задавать 149 явно.
- `docs/BUSINESS.md` — только MTProxy Stars price в monetization table и gift
  certificate rule.
- `docs/CONTRACTS.md` — только `stars_price: 99` в существующем MTProxy product
  response example; поля и shape не меняются.

## Dependency and Batch Graph

```text
MTS99-B1 (one implementer, sequential):
MTS99-001 -> MTS99-002 -> read-only batch review -> root verification
```

Параллельной реализации нет. Оба пункта образуют одну согласованную смену цены:
сначала фиксируется пользовательское отображение и отправляемая сумма, затем
backend-to-bot/test-product representations и документы. Второй пункт
начинается только после targeted GREEN первого.

---

### Task 1: MTS99-001 — Согласовать bot display и Stars invoices на 99

**Result:** FAQ, экран и клавиатура способов оплаты подписки и клавиатура
подарочного сертификата показывают 99 ★; subscription и gift handlers получают
текущий invoice fixture 99 и отправляют его как 99 XTR без изменения routing,
payload или handler logic.

**Requirements:** BR-001, BR-002; AC-001, AC-002, AC-003, bot-handler часть
AC-005.

**Dependencies:** approved `business.md`, `scope_revision: 2`; заключение root
agent об отсутствии architecture changes; незавершённых code dependencies нет.

**Files and ownership:**

- Modify/Test: `bot/tests/test_handlers.py` — только assertions/fixtures в
  существующих info, payment screen, gift screen, subscription Stars invoice и
  gift Stars invoice tests.
- Modify: `bot/src/messages.py` — только два MTProxy Stars literals `80` → `99`
  в `FAQ_TEXT` и `PAYMENT_METHODS_TEXT`; соседний copy не менять.
- Modify: `bot/src/keyboards.py` — только Stars labels в `payment_methods()` и
  `gift_certificate_payment_methods()`; callbacks, styles, row order, ЮKassa и
  `vpn_payment_methods()` не менять.

**Documentation:** Для этого пункта документационные файлы не изменяются;
актуализация утверждённых `docs/BUSINESS.md` и `docs/CONTRACTS.md` принадлежит
MTS99-002, чтобы не размывать владение файлами внутри последовательной партии.

**Interfaces:**

- Consumes: неизменные `process_info`, `process_boost_paid`,
  `process_gift_certificate`, `process_pay_stars` и `process_gift_stars`, а
  также существующий `StarsInvoice.prices` forwarding contract.
- Produces: exact visible label `⭐ Telegram Stars — 99 ★`, copy mentioning
  `99 ★`, and subscription/gift `send_invoice(... currency="XTR",
  prices=[LabeledPrice(..., amount=99)])`; Python signatures remain unchanged.

- [ ] **RED — сначала расширить существующие assertions и обновить current-price
  invoice fixtures.** В `bot/tests/test_handlers.py`:

  - в `test_info_answers_callback` получить первый `text` из
    `callback.message.edits` и проверить наличие `99 ★` и отсутствие `80 ★`;
  - в `test_payment_screen_includes_legal_links` также получить `markup`,
    проверить `99 ★/месяц` в тексте и exact второй button
    `⭐ Telegram Stars — 99 ★`;
  - в `test_gift_certificate_screen_shows_payment_options` проверить exact
    Stars button `⭐ Telegram Stars — 99 ★`, сохранив callback assertions;
  - в `test_pay_stars_sends_xtr_invoice` заменить fixture amount и expected
    amount с 80 на 99;
  - в `test_gift_stars_invoice_uses_gift_payload` заменить fixture amount на 99
    и добавить `assert invoice["prices"][0].amount == 99`.

  Не менять FakeBot/FakePayments, handler implementation или VPN fixtures.

- [ ] **Запустить RED и подтвердить причину.** Из корня репозитория:

  ```bash
  cd bot && uv run pytest tests/test_handlers.py \
    -k "info_answers_callback or payment_screen_includes_legal_links or gift_certificate_screen_shows_payment_options or pay_stars_sends_xtr_invoice or gift_stars_invoice_uses_gift_payload" -q
  ```

  Ожидаемый результат до production-copy изменений: display assertions падают,
  потому что FAQ/payment/gift labels ещё содержат 80 ★. Invoice forwarding
  assertions с fixture amount 99 уже могут пройти: они фиксируют неизменный
  pass-through contract, а не требуют новой handler logic.

- [ ] **GREEN — выполнить минимальные presentation substitutions.** Заменить
  ровно четыре пользовательских MTProxy literals:

  ```text
  bot/src/messages.py: FAQ_TEXT и PAYMENT_METHODS_TEXT — 80 ★ -> 99 ★
  bot/src/keyboards.py: payment_methods() и
  gift_certificate_payment_methods() — 80 ★ -> 99 ★
  ```

  Не выносить цену в constant/configuration и не менять динамическую VPN
  keyboard.

- [ ] **Подтвердить targeted GREEN.** Повторить RED-команду и получить PASS;
  subscription и gift invoices должны сохранить `currency == "XTR"`, свои
  прежние payloads и иметь `prices[0].amount == 99`.

- [ ] **Проверить весь затронутый handler module.** Выполнить:

  ```bash
  cd bot && uv run pytest tests/test_handlers.py -q
  ```

  **Completion criterion:** targeted и весь handler test module зелёные; FAQ,
  subscription и gift screens содержат 99 ★; оба XTR invoice scenarios
  используют 99; diff пункта ограничен тремя назначенными файлами и не меняет
  callbacks, payloads, handlers, ЮKassa или VPN.

---

### Task 2: MTS99-002 — Согласовать current-product fixtures и документацию

**Result:** backend-to-bot fixture, `create_test_product`, текущий MTProxy
`ProductFactory`, business rules и MTProxy API response example используют 99
Stars, при этом generic model default и исторические данные 80 остаются
неизменными.

**Requirements:** BR-003; AC-004, AC-005, AC-006; поддерживает invoice contract
из BR-001/BR-002.

**Dependencies:** MTS99-001 targeted GREEN; approved предусловие, что saved
`mtproto_30d.stars_price` уже равно 99.

**Files and ownership:**

- Modify/Test: `bot/tests/domains/payments/test_client.py` — только MTProxy
  `PRODUCT_JSON["stars_price"]` и expected `LabeledPrice.amount`; VPN fixture
  override 149 не менять.
- Modify: `src/apps/payments/models.py` — только `stars_price` argument в
  `ProductQuerySet.create_test_product`; `Product` fields и остальной helper не
  менять.
- Modify: `src/apps/payments/tests/factories.py` — только explicit
  `ProductFactory.stars_price`; other factories не менять.
- Modify: `docs/BUSINESS.md` — только две MTProxy Stars цены: monetization table
  и gift certificate paragraph.
- Modify: `docs/CONTRACTS.md` — только значение `stars_price` в существующем
  `GET /payments/` MTProxy example.

**Interfaces:**

- Consumes: неизменный `PaymentsClient.get_stars_invoice()` mapping
  `data["stars_price"] -> LabeledPrice.amount` и существующий Product API shape.
- Produces: MTProxy test representations with `stars_price = 99` and unchanged
  invoice/API shapes; `Product.stars_price` field still defaults to 80.

- [ ] **RED — сначала изменить только invoice expectation.** В
  `test_get_stars_invoice_maps_fields` заменить expected
  `LabeledPrice(..., amount=80)` на `amount=99`, пока `PRODUCT_JSON` ещё
  содержит `"stars_price": 80`.

- [ ] **Запустить RED и подтвердить точную причину.** Из корня:

  ```bash
  cd bot && uv run pytest \
    tests/domains/payments/test_client.py::test_get_stars_invoice_maps_fields -q
  ```

  Ожидаемый результат: FAIL — фактически mapped amount равен входному fixture
  value 80, а expected current MTProxy price равен 99. Не менять client logic.

- [ ] **GREEN — обновить источник fixture.** В `PRODUCT_JSON` заменить только
  `"stars_price": 80` на `"stars_price": 99`; повторить команду и получить
  PASS. Существующий mapping должен пройти без production client changes.

- [ ] **Согласовать backend test representations.** Выполнить только две
  literal substitutions:

  ```python
  # src/apps/payments/models.py, only in create_test_product()
  stars_price=99,

  # src/apps/payments/tests/factories.py, only ProductFactory
  stars_price = 99
  ```

  Не изменять `stars_price = models.PositiveIntegerField(..., default=80)` и не
  добавлять migration/schema/data write. Проверить factory through existing API
  tests:

  ```bash
  make test ARGS="apps.payments.tests.test_views.test_get_product_view apps.payments.tests.test_models"
  ```

- [ ] **Синхронизировать approved documentation.** В `docs/BUSINESS.md`
  заменить 80 ★ на 99 ★ только в MTProxy monetization row и gift certificate
  paragraph. В `docs/CONTRACTS.md` заменить только `"stars_price": 80` на 99 в
  существующем MTProxy `GET /payments/` example. Не менять RUB, VPN, fields,
  endpoint semantics или `docs/MODELS.md`.

- [ ] **Выполнить targeted GREEN пункта.** Из корня:

  ```bash
  cd bot && uv run pytest tests/domains/payments/test_client.py -q
  make test ARGS="apps.payments.tests.test_views.test_get_product_view apps.payments.tests.test_models"
  git diff --check
  ```

  **Completion criterion:** PaymentsClient maps current fixture 99 to invoice
  amount 99; backend tests using the updated ProductFactory pass;
  `create_test_product` and ProductFactory explicitly use 99; оба документа
  show 99 only for MTProxy Stars; field default, migrations, migration tests,
  `docs/MODELS.md`, RUB and VPN remain unchanged.

## Task Packet MTS99-B1

- **scope_revision:** 2; revision 1 packets and migration/default assumptions
  are superseded and forbidden.
- **Plan item IDs:** `MTS99-001`, затем `MTS99-002`; один
  `plan-implementer`, максимум два пункта, строго последовательное выполнение.
- **Assigned BR/AC:** MTS99-001 — BR-001, BR-002; AC-001, AC-002, AC-003 и bot
  handler часть AC-005. MTS99-002 — BR-003; AC-004, AC-005, AC-006 и сохранение
  mapping contract для BR-001/BR-002.
- **Allowed and expected files:** `bot/src/keyboards.py`,
  `bot/src/messages.py`, `bot/tests/test_handlers.py`,
  `bot/tests/domains/payments/test_client.py`, `src/apps/payments/models.py`,
  `src/apps/payments/tests/factories.py`, `docs/BUSINESS.md`,
  `docs/CONTRACTS.md`.
- **Ownership boundary:** только MTProxy price display/copy, соответствующие
  handler/client assertions и fixtures, два explicit test-product price values
  и три документированных MTProxy price occurrences. `plan.md` принадлежит
  planner/root и implementer-ом не редактируется.
- **Forbidden adjacent work:** любые другие files; `Product.stars_price` field
  declaration/default; `docs/MODELS.md`; migrations и `test_migrations.py`;
  database writes; API/client/handler/payment logic; callbacks/payloads;
  successful payment flow; VPN/RUB; abstractions/refactors/dependencies;
  `apps/music/`; branch/commit/push/PR/merge/deploy.
- **Non-goals:** создание актуальной saved price, schema/data migration,
  configurable/shared price source, новые plans/tariffs/providers, изменение
  duration или contract shape, hardening и соседняя cleanup.
- **Dependencies:** approved `business.md` revision 2 и root conclusion «no
  architecture change»; MTS99-002 starts only after MTS99-001 targeted GREEN.
- **Budget:** восемь modified implementation files, ноль новых implementation
  files; четыре user-visible literal replacements, две MTProxy invoice fixture/
  expectation alignments с focused assertions, два explicit test-product
  literals и три documentation value replacements. Ноль новой logic.
- **Completion criterion:** оба task completion criteria выполнены, только
  allowed files изменены, и все integration checks ниже успешны; remaining
  price-related 80 occurrences совпадают только с утверждённым legacy/default
  списком.

## Root Integration Verification

После batch implementation и read-only review главный оркестратор выполняет из
корня репозитория:

```bash
(cd bot && uv run pytest tests/test_handlers.py tests/domains/payments/test_client.py -q)
(cd bot && uv run pytest)
make test ARGS="apps.payments.tests.test_views.test_get_product_view apps.payments.tests.test_models"
make test
docker compose -f docker-compose.yml config --quiet
git diff --check
rg -n '(80 ★|amount=80|stars_price["'"': =]+80|default=80\b|default: 80\b)' \
  bot/src bot/tests src/apps/payments \
  docs/BUSINESS.md docs/CONTRACTS.md docs/MODELS.md
```

Ожидания: targeted и полные bot/Django suites PASS, production Compose config
валиден, `git diff --check` без вывода. Последний audit не находит актуальных
bot/current-product/docs price remnants; его price-related 80 results должны
состоять только из:

- `src/apps/payments/models.py` — `Product.stars_price` field `default=80`;
- `src/apps/payments/migrations/0004_alter_product_stars_price.py` —
  исторический default;
- `src/apps/payments/tests/test_migrations.py` — историческое setup-значение
  `stars_price=80`;
- `docs/MODELS.md` — корректное описание generic field default 80.

Root также сверяет `git diff --name-only` с восемью allowed implementation
files и этим feature artifact. Любое другое изменение, migration/schema/data
write, изменение RUB/VPN или отсутствие одного из ожидаемых legacy 80 означает,
что batch не завершён и должен быть возвращён implementer-у как
`blocking_in_scope`.
