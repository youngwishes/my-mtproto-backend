# Product Main Menu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

- **Status:** approved
- **Scope revision:** 1
- **Route:** small local feature; the root agent approved the conclusion that
  no architecture document or architecture review stage is required.

**Goal:** После действующего юридического согласия показывать корневой выбор
между MTProxy и VPN, открывать отдельные продуктовые меню и возвращать
пользователя назад в контексте выбранного продукта.

**Architecture:** Изменение остаётся внутри aiogram presentation layer. Текущий
callback `vpn` продолжает открывать существующий экран статуса/покупки/продления,
а новые callbacks `show_mtproxy_menu` и `show_vpn_menu` открывают продуктовые
меню; `show_start_screen` остаётся возвратом в корень. Backend API, модели,
платёжные handlers и domain clients не меняются.

**Tech Stack:** Python 3.13, aiogram 3, pytest/pytest-asyncio, существующие
`FakeMessage`, `FakeCallback`, `FakeFreeTrial` и `FakeVPN`.

## Global Constraints

- Единственный источник обязательных требований — approved
  `docs/features/product-main-menu/business.md`, `scope_revision: 1`.
- Production-код изменяется только после соответствующего RED-теста: RED →
  минимальный GREEN → локальный refactor только на зелёном тесте.
- Существующие тексты MTProxy и VPN status/purchase/renewal не переписывать;
  новые тексты ограничены утверждёнными точками продуктовой навигации.
- Не менять backend API, модели, migrations, цены, payment payloads, invoice
  routing, юридическое согласие или регистрацию реферала.
- Не добавлять VPN-тарифы, статусы, зависимости, новые модули или общие
  keyboard/handler abstractions.
- Не изменять действующие callbacks продуктовых действий:
  `boost_free`, `boost_paid`, `my_servers`, `gift_certificate`, `referral`,
  `info`, `vpn`, `vpn_pay_yukassa`, `vpn_pay_stars`.
- `apps/music/` не читать и не изменять.
- Один implementer получает не более двух пунктов. Из-за пересечения
  `bot/src/keyboards.py` и `bot/tests/test_handlers.py` batches выполняются
  только последовательно.
- Implementers не создают ветки, commits, push, PR, merge или deploy; эти gates
  остаются у главного оркестратора по `docs/DEVELOPMENT_WORKFLOW.md`.

## File and Interface Map

- `bot/src/messages.py` — только два новых presentation constants:
  `PRODUCT_MENU_TEXT` и `VPN_PRODUCT_MENU_TEXT`; существующие welcome/VPN
  status constants остаются byte-for-byte неизменными.
- `bot/src/keyboards.py` — корневое, MTProxy и VPN product menus, а также три
  явных направления возврата: root, MTProxy и VPN.
- `bot/src/handlers/start.py` — `/start`, consent completion, root callback и
  вход в MTProxy с free-period check на каждом входе.
- `bot/src/handlers/vpn.py` — новый лёгкий product-menu handler; существующий
  `process_vpn` остаётся единственной точкой загрузки VPN status/prices.
- `bot/tests/test_handlers.py` — RED/GREEN handler и keyboard contracts с
  существующими fakes; новый test framework или новые fake-модули не нужны.
- `docs/features/product-main-menu/acceptance.md` — создаётся главным
  оркестратором после реализации и независимого product review; implementer
  batches этим файлом не владеют.

## Dependency and Batch Graph

```text
Batch PMM-B1 (one implementer): PMM-001 -> PMM-002 -> read-only batch review
Batch PMM-B2 (one implementer): PMM-003             -> read-only batch review

PMM-B1 -> PMM-B2 -> full verification -> product review -> acceptance.md
```

Параллельных batches нет: оба изменяют `bot/src/keyboards.py` и
`bot/tests/test_handlers.py`.

---

### Task 1 (PMM-001): Корневой выбор продукта и вход в MTProxy

**Result:** `/start`, успешное принятие юридического согласия и
`show_start_screen` показывают только нейтральный корень, не проверяя бесплатный
период. `show_mtproxy_menu` на каждом вызове выполняет существующий free-period
check и показывает прежний welcome text с MTProxy-действиями в утверждённом
порядке.

**Requirements:** BR-001..BR-004, BR-009; AC-001..AC-003, AC-007.

**Dependencies:** approved `business.md`, `scope_revision: 1`; незавершённых
code dependencies нет.

**Files and ownership:**

- Modify: `bot/src/messages.py` — только `PRODUCT_MENU_TEXT`.
- Modify: `bot/src/keyboards.py` — `_ROOT_BACK`, `product_menu()` и
  `mtproxy_menu(boost_callback_data)`; не менять callbacks внутренних экранов в
  этом пункте.
- Modify: `bot/src/handlers/start.py` — разделить root rendering и MTProxy
  rendering; consent/referral flow менять только в его конечном destination.
- Modify/Test: `bot/tests/test_handlers.py` — только start/consent/MTProxy menu
  tests и прежние `main_menu` keyboard tests.

**Interfaces produced:**

- Constant: `PRODUCT_MENU_TEXT = "Выберите продукт"`.
- Root Back button: `_ROOT_BACK` with text `🔙 Назад` and callback
  `show_start_screen`.
- Keyboards: `product_menu() -> InlineKeyboardMarkup` and
  `mtproxy_menu(boost_callback_data: str) -> InlineKeyboardMarkup`.
- Renderers: `_render_start_screen() -> tuple[str, InlineKeyboardMarkup]` and
  async `_render_mtproxy_menu(*, deps: Dependencies, telegram_id: str,
  telegram_username: str | None) -> tuple[str, InlineKeyboardMarkup]`.
- Handlers: async `cmd_start_inline(callback: CallbackQuery) -> None` and
  `process_mtproxy_menu(callback: CallbackQuery, deps: Dependencies) -> None`.

`product_menu()` имеет ровно две строки:

```python
[
    [InlineKeyboardButton(
        text="⚡ MTProxy", callback_data="show_mtproxy_menu", style="primary"
    )],
    [InlineKeyboardButton(
        text="🔐 VPN", callback_data="show_vpn_menu", style="primary"
    )],
]
```

`mtproxy_menu()` сохраняет существующие labels/callbacks/URLs и формирует строки
в точном порядке:

```python
[
    ["⚡️ Ускорить Telegram"],
    ["📡 Мои серверы"],
    ["🎁 Подарить подписку"],
    ["🤝 Реферальный кабинет"],
    ["📋 Информация"],
    ["💬 Поддержка", "🌐 Наш сайт"],
    ["🔙 Назад"],
]
```

- [ ] **RED — переписать stale start tests и добавить новый MTProxy contract.**
  В `bot/tests/test_handlers.py` импортировать `process_mtproxy_menu`,
  `PRODUCT_MENU_TEXT`, `WELCOME_TEXT_MONTH` и `WELCOME_TEXT_NOT_FREE`.
  Заменить tests, которые ожидают free-trial check непосредственно из
  `cmd_start`, на следующие проверки:

  ```python
  async def test_cmd_start_shows_only_product_root_without_free_trial_check():
      fake = FakeFreeTrial(check="MONTH")
      message = FakeMessage(text="/start", user_id=42, username="bob")

      await cmd_start(message, make_deps(free_trial=fake))

      assert fake.status_checked == ["42"]
      assert fake.checked == []
      text, markup = message.answers[0]
      assert text == PRODUCT_MENU_TEXT
      assert [[button.text for button in row] for row in markup.inline_keyboard] == [
          ["⚡ MTProxy"],
          ["🔐 VPN"],
      ]
      assert [
          [button.callback_data for button in row]
          for row in markup.inline_keyboard
      ] == [["show_mtproxy_menu"], ["show_vpn_menu"]]

  @pytest.mark.parametrize(
      ("period", "expected_text", "boost_callback"),
      [
          ("MONTH", WELCOME_TEXT_MONTH, "boost_free"),
          ("NOT_AVAILABLE", WELCOME_TEXT_NOT_FREE, "boost_paid"),
      ],
  )
  async def test_mtproxy_menu_checks_free_period_on_every_entry(
      period, expected_text, boost_callback
  ):
      fake = FakeFreeTrial(check=period)
      callback = FakeCallback(user_id=42, username="real_user")
      deps = make_deps(free_trial=fake)

      await process_mtproxy_menu(callback, deps)
      await process_mtproxy_menu(callback, deps)

      assert fake.checked == [
          ("42", "real_user", None),
          ("42", "real_user", None),
      ]
      text, markup = callback.message.edits[-1]
      assert text == expected_text
      assert markup.inline_keyboard[0][0].callback_data == boost_callback
      assert [[button.text for button in row] for row in markup.inline_keyboard] == [
          ["⚡️ Ускорить Telegram"],
          ["📡 Мои серверы"],
          ["🎁 Подарить подписку"],
          ["🤝 Реферальный кабинет"],
          ["📋 Информация"],
          ["💬 Поддержка", "🌐 Наш сайт"],
          ["🔙 Назад"],
      ]
  ```

  Обновить `test_accept_consent_registers_clicking_user_and_opens_start_screen`:
  сохранить exact assertion
  `fake.accepted == [("42", "real_user", "777")]`, заменить прежнее ожидание
  availability check на `fake.checked == []`, затем проверить
  `text == PRODUCT_MENU_TEXT` и те же две root buttons. Сохранить tests, что
  self-referral не попадает в consent callback и backend `False` не открывает
  меню. Удалить только stale assertions, которые связывали root с availability:

  - `test_cmd_start_passes_none_username_as_none_not_string` перенести на
    `process_mtproxy_menu` и ожидать
    `fake.checked == [("42", None, None)]`;
  - `test_cmd_start_extracts_referrer_from_payload` покрыт более точным
    `test_cmd_start_carries_referrer_in_consent_callback`, который сохраняет
    callback `accept_legal_terms:777` до consent;
  - `test_cmd_start_ignores_self_referral` запускать с `consent=False` и ожидать
    callback ровно `accept_legal_terms`;
  - оба `show_start_screen` tests вызывать как `await cmd_start_inline(callback)`:
    первый сохраняет assertion `callback.answers`, второй проверяет
    `text == PRODUCT_MENU_TEXT` и callbacks
    `[["show_mtproxy_menu"], ["show_vpn_menu"]]` вместо данных нажавшего для
    удалённого availability check;
  - `test_main_menu_last_button_links_to_site` и
    `test_main_menu_has_support_button` переименовать в MTProxy menu tests,
    строить `keyboards.mtproxy_menu("boost_free")` и проверять, что множество
    URL содержит одновременно `SITE_URL` и `SUPPORT_URL` (site больше не
    является последней кнопкой из-за root Back);
  - удалить stale `test_main_menu_opens_vpn_subscription_management`: прямого
    `vpn` callback в MTProxy menu больше нет, а новый переход
    root `show_vpn_menu` уже проверяется exact root contract выше.

- [ ] **Запустить RED.**

  ```bash
  cd bot && uv run pytest tests/test_handlers.py \
    -k "cmd_start or accept_consent or show_start_screen or mtproxy_menu or main_menu" -q
  ```

  Ожидаемый результат до production-изменений: FAIL, потому что root всё ещё
  показывает welcome/старое общее меню, вызывает `check_availability`, а
  `process_mtproxy_menu`, `product_menu` и `mtproxy_menu` отсутствуют.

- [ ] **GREEN — внести минимальное production-изменение.** В
  `messages.py` добавить только `PRODUCT_MENU_TEXT`. В `keyboards.py` заменить
  `main_menu()` двумя функциями выше, переиспользовать `_MY_SERVERS`,
  `SUPPORT_URL`, `SITE_URL` и существующие callbacks. В `start.py`:

  ```python
  def _render_start_screen() -> tuple[str, InlineKeyboardMarkup]:
      return PRODUCT_MENU_TEXT, keyboards.product_menu()

  async def _render_mtproxy_menu(
      *, deps, telegram_id, telegram_username
  ) -> tuple[str, InlineKeyboardMarkup]:
      available_free_period = await deps.free_trial.check_availability(
          telegram_id=telegram_id,
          telegram_username=telegram_username,
          invited_from_username=None,
      )
      text = FREE_AVAILABLE_TEXT_MAPPING.get(available_free_period)
      is_free = available_free_period != FreeAvailable.NOT_AVAILABLE
      boost_callback_data = "boost_free" if is_free else "boost_paid"
      return text, keyboards.mtproxy_menu(boost_callback_data)
  ```

  `cmd_start` по-прежнему парсит referrer, проверяет consent и для нового
  пользователя вкладывает referrer в `legal_consent()` callback. При принятом
  consent он вызывает только `_render_start_screen()`. `process_legal_consent`
  сохраняет вызов `deps.free_trial.accept_consent` с полями `telegram_id`,
  `telegram_username` и `invited_from_username`, после `accepted is True` также
  показывает `_render_start_screen()`. `cmd_start_inline` отвечает на callback
  и показывает root без `Dependencies`. Новый handler с фильтром
  `F.data == "show_mtproxy_menu"` отвечает на callback, вызывает
  `_render_mtproxy_menu()` с `callback.from_user.id/username` и редактирует
  текущее сообщение.

- [ ] **Documentation:** approved `business.md` и глобальные docs не менять;
  новое поведение уже полностью задано BR/AC, а архитектурное изменение явно не
  требуется. Acceptance evidence будет записана root-агентом после product
  review.

- [ ] **GREEN verification.**

  ```bash
  cd bot && uv run pytest tests/test_handlers.py \
    -k "cmd_start or accept_consent or show_start_screen or mtproxy_menu or main_menu" -q
  ```

  Ожидаемый результат: выбранные tests PASS; существующие consent tests
  подтверждают неизменную передачу referrer, а новые tests — отсутствие
  free-trial check в root и два check-вызова на два входа в MTProxy.

**Completion criterion:** Root содержит ровно две утверждённые кнопки; `/start`,
consent completion и root-back не вызывают availability check; каждый MTProxy
entry вызывает его с данными нажавшего пользователя и показывает прежний
welcome/free-period text и семь keyboard rows в заданном порядке.

---

### Task 2 (PMM-002): Контекстный возврат из внутренних экранов MTProxy

**Result:** Каждая уже существующая кнопка `🔙 Назад` на внутренних экранах
MTProxy возвращает в `show_mtproxy_menu`; `🔙 Отмена` перевыпуска по-прежнему
возвращает в `my_servers`, а новые return actions не добавляются.

**Requirements:** BR-005, BR-010; AC-004, AC-008.

**Dependencies:** PMM-001 (`show_mtproxy_menu` и `_ROOT_BACK`).

**Files and ownership:**

- Modify: `bot/src/keyboards.py` — только `_MTPROXY_BACK` и его использование
  шестью существующими MTProxy keyboard factories.
- Modify/Test: `bot/tests/test_handlers.py` — один keyboard contract; не менять
  handlers или VPN tests.

**Interface produced:**

```python
_MTPROXY_BACK = InlineKeyboardButton(
    text="🔙 Назад", callback_data="show_mtproxy_menu"
)
```

Его используют только `key_generated()`, `my_servers()`, `info()`,
`payment_methods()`, `gift_certificate_payment_methods()` и
`referral_cabinet()`. `confirm_reissue()` сохраняет callback `my_servers`;
`vpn_payment_methods()` пока сохраняет `_ROOT_BACK` до PMM-003.

- [ ] **RED — добавить исчерпывающий contract существующих Back buttons.**

  ```python
  def test_mtproxy_internal_back_buttons_return_to_mtproxy_menu(
      servers: MyServers,
  ):
      markups = {
          "key_generated": keyboards.key_generated(),
          "my_servers": keyboards.my_servers(servers.servers),
          "info": keyboards.info(),
          "payment_methods": keyboards.payment_methods(),
          "gift_certificate": keyboards.gift_certificate_payment_methods(),
          "referral_cabinet": keyboards.referral_cabinet(
              active_referrals_count=4,
              referral_link="https://t.me/bot?start=42",
          ),
      }

      assert {
          name: markup.inline_keyboard[-1][0].callback_data
          for name, markup in markups.items()
      } == {name: "show_mtproxy_menu" for name in markups}
      assert keyboards.confirm_reissue().inline_keyboard[-1][0].callback_data \
          == "my_servers"
  ```

- [ ] **Запустить RED.**

  ```bash
  cd bot && uv run pytest \
    tests/test_handlers.py::test_mtproxy_internal_back_buttons_return_to_mtproxy_menu -q
  ```

  Ожидаемый результат до production-изменения: FAIL с фактическим
  `show_start_screen` вместо `show_mtproxy_menu`.

- [ ] **GREEN — добавить `_MTPROXY_BACK` и заменить им только шесть перечисленных
  `_ROOT_BACK` usages.** Не менять тексты экранов, действие reissue cancel,
  server URLs, payment callbacks, referral threshold или порядок остальных
  кнопок.

- [ ] **Documentation:** документы не меняются; это прямая реализация
  BR-005/AC-004 без нового сценария. Зафиксировать доказательство в будущем
  `acceptance.md`, но не создавать его в implementer batch.

- [ ] **GREEN verification.**

  ```bash
  cd bot && uv run pytest \
    tests/test_handlers.py::test_mtproxy_internal_back_buttons_return_to_mtproxy_menu \
    tests/test_handlers.py::test_update_link_shows_confirmation_without_reissuing \
    tests/test_handlers.py::test_confirm_reissue_reissues_and_shows_servers_with_banner -q
  ```

  Ожидаемый результат: все выбранные tests PASS; existing reissue behavior
  остаётся зелёным.

**Completion criterion:** Все шесть существующих MTProxy `🔙 Назад` buttons
имеют callback `show_mtproxy_menu`, а вложенный reissue cancel по-прежнему имеет
callback `my_servers`; других keyboard changes в diff нет.

---

### Task 3 (PMM-003): Вложенное VPN-меню и контекстный возврат

**Result:** Root VPN button открывает лёгкое меню только с `Купить ВПН` и
`🔙 Назад`; покупка через сохранённый callback `vpn` открывает прежний
status/purchase/renewal screen, а его Back button возвращает в VPN product menu.

**Requirements:** BR-006..BR-008, BR-010; AC-005, AC-006, AC-008.

**Dependencies:** PMM-001 и PMM-002 завершены и прошли batch review.

**Files and ownership:**

- Modify: `bot/src/messages.py` — только `VPN_PRODUCT_MENU_TEXT`; не менять
  `VPN_MENU_TEXT`, `VPN_EXPIRED_TEXT`, `VPN_ACTIVE_TEXT` или
  `VPN_PURCHASED_TEXT`.
- Modify: `bot/src/keyboards.py` — `_VPN_BACK`, `vpn_menu()` и Back target в
  `vpn_payment_methods()`; не менять price formatting/payment callbacks.
- Modify: `bot/src/handlers/vpn.py` — только новый `process_vpn_menu`; тело и
  filter существующего `process_vpn` не менять.
- Modify/Test: `bot/tests/test_handlers.py` — VPN product-menu/back contracts и
  exact regression assertions для существующих status texts/payment callbacks.

**Interfaces produced:**

```python
# bot/src/messages.py
VPN_PRODUCT_MENU_TEXT = """🔐 <b>VPN</b>

Выберите действие:"""

# bot/src/keyboards.py
_VPN_BACK = InlineKeyboardButton(
    text="🔙 Назад", callback_data="show_vpn_menu"
)

def vpn_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Купить ВПН", callback_data="vpn")],
            [_ROOT_BACK],
        ]
    )

```

Handler interface: async
`process_vpn_menu(callback: CallbackQuery) -> None`, отфильтрованный exact
callback value `show_vpn_menu`; его полное тело задано в GREEN-шаге ниже.

- [ ] **RED — добавить product-menu и contextual-back tests.** Импортировать
  `process_vpn_menu` и `VPN_PRODUCT_MENU_TEXT`. Добавить:

  ```python
  async def test_vpn_product_menu_contains_only_buy_and_root_back():
      callback = FakeCallback(data="show_vpn_menu")

      await process_vpn_menu(callback)

      assert callback.answers
      text, markup = callback.message.edits[0]
      assert text == VPN_PRODUCT_MENU_TEXT
      assert [[button.text for button in row] for row in markup.inline_keyboard] == [
          ["Купить ВПН"],
          ["🔙 Назад"],
      ]
      assert [
          [button.callback_data for button in row]
          for row in markup.inline_keyboard
      ] == [["vpn"], ["show_start_screen"]]
  ```

  В существующем parameterized VPN status test для `none`, `expired`, `active`
  вычислить exact expected text из неизменённых constants:

  ```python
  expected_text = {
      "none": VPN_MENU_TEXT,
      "expired": VPN_EXPIRED_TEXT.format(expired_at=expired_at),
      "active": VPN_ACTIVE_TEXT.format(
          expired_at=expired_at,
          subscription_url=subscription_url,
      ),
  }[status]
  assert text == expected_text
  assert markup.inline_keyboard[-1][0].callback_data == "show_vpn_menu"
  assert "vpn_pay_yukassa" in callbacks
  assert "vpn_pay_stars" in callbacks
  ```

  Сохранить существующие tests exact invoice payloads `vpn_yukassa` и
  `vpn_stars`, текущих цен и successful-payment routing без изменений.

- [ ] **Запустить RED.**

  ```bash
  cd bot && uv run pytest tests/test_handlers.py \
    -k "vpn_product_menu or vpn_menu or vpn_purchase_screen" -q
  ```

  Если существующие VPN tests переименованы из `vpn_menu` в
  `vpn_purchase_screen`, `-k` намеренно покрывает оба имени. Ожидаемый результат
  до production-изменения: FAIL из-за отсутствующего `process_vpn_menu` и Back
  callback `show_start_screen` вместо `show_vpn_menu`.

- [ ] **GREEN — минимально добавить presentation menu.** Добавить
  `VPN_PRODUCT_MENU_TEXT`, `vpn_menu()` и handler:

  ```python
  @router.callback_query(F.data == "show_vpn_menu")
  async def process_vpn_menu(callback: CallbackQuery) -> None:
      await callback.answer()
      await callback.message.edit_text(
          text=VPN_PRODUCT_MENU_TEXT,
          reply_markup=keyboards.vpn_menu(),
      )
  ```

  В `vpn_payment_methods()` заменить только последнюю `_ROOT_BACK` на
  `_VPN_BACK`. Существующий `@router.callback_query(F.data == "vpn")`
  `process_vpn`, оба invoice handlers и successful-payment routing не менять.

- [ ] **Documentation:** глобальные business/architecture/contracts/models docs
  не меняются, потому что status, API и payment contracts остаются прежними.
  Acceptance evidence добавит root-агент после независимого product review.

- [ ] **GREEN verification.**

  ```bash
  cd bot && uv run pytest tests/test_handlers.py -k "vpn" -q
  ```

  Ожидаемый результат: VPN product-menu, status variants, current-price,
  invoice payload и successful-payment tests PASS.

**Completion criterion:** `show_vpn_menu` не вызывает backend или invoice APIs и
рендерит ровно две кнопки; `vpn` по-прежнему один раз загружает существующие
menu/prices и показывает byte-for-byte прежний status text; Back с этого экрана
имеет callback `show_vpn_menu`, а VPN product Back — `show_start_screen`.

## Task Packets

### PMM-B1 — Root/MTProxy navigation

- `scope_revision`: 1.
- Plan IDs: `PMM-001`, затем `PMM-002`; один implementer, не более двух
  пунктов.
- Assigned BR/AC: BR-001..BR-005, BR-009..BR-010; AC-001..AC-004,
  AC-007..AC-008.
- Allowed and expected files:
  `bot/src/messages.py`, `bot/src/keyboards.py`, `bot/src/handlers/start.py`,
  `bot/tests/test_handlers.py`.
- Ownership boundary: product root, MTProxy entry/free-period rendering и
  targets уже существующих MTProxy Back buttons. Не менять VPN handler/menu
  logic в этом batch.
- Forbidden neighboring work: `bot/src/domains/**`, `bot/src/handlers/vpn.py`,
  `bot/src/handlers/payments.py`, backend `src/**`, другие tests/docs,
  dependency/formatting refactors, branch/commit/push/PR/merge/deploy.
- Non-goals: API/models/migrations/prices/payment behavior; VPN tariff/status;
  legal/referral behavior; новые return buttons; unrelated refactors;
  `apps/music/`.
- Dependencies: approved scope revision 1; PMM-002 начинается только после
  GREEN PMM-001.
- Budget: максимум четыре изменяемых файла, никаких новых файлов/modules/deps;
  только две presentation functions, один MTProxy handler, разделение одного
  renderer и contextual replacement существующих Back callbacks.
- Verifiable completion: targeted PMM-001/PMM-002 commands GREEN, затем
  `cd bot && uv run pytest tests/test_handlers.py -q` GREEN; diff содержит только
  назначенные root/MTProxy изменения. После implementer остановить writes и
  передать batch отдельному read-only `code-reviewer`.

### PMM-B2 — VPN navigation

- `scope_revision`: 1.
- Plan IDs: `PMM-003`; один implementer.
- Assigned BR/AC: BR-006..BR-008, BR-010; AC-005..AC-006, AC-008.
- Allowed and expected files:
  `bot/src/messages.py`, `bot/src/keyboards.py`, `bot/src/handlers/vpn.py`,
  `bot/tests/test_handlers.py`.
- Ownership boundary: VPN product text/menu handler и два Back targets; current
  `process_vpn` status/prices/payment behavior только покрыть regression tests.
- Forbidden neighboring work: `bot/src/domains/**`,
  `bot/src/handlers/payments.py`, backend `src/**`, другие tests/docs,
  invoice/payment refactors, branch/commit/push/PR/merge/deploy.
- Non-goals: новые VPN tariff/status/text for status, price/payment changes,
  backend/API/model/migration changes, новые общие abstractions, unrelated
  refactors, `apps/music/`.
- Dependencies: PMM-B1 завершён, его read-only review не содержит подтверждённых
  `blocking_in_scope`.
- Budget: максимум четыре изменяемых файла, никаких новых files/modules/deps;
  один constant, одна keyboard factory, один thin handler и одна Back target
  replacement.
- Verifiable completion: PMM-003 targeted command и
  `cd bot && uv run pytest tests/test_handlers.py -q` GREEN; exact existing VPN
  texts, price buttons, invoice payloads и payment routing остаются зелёными.
  После implementer остановить writes и передать batch новому read-only
  `code-reviewer`.

## Integration, Product Review and Release Gates

После обоих batch reviews главный оркестратор выполняет:

```bash
(cd bot && uv run pytest)
make test
docker compose -f docker-compose.yml config --quiet
git diff --check
```

Ожидания: весь bot suite и Django suite PASS, production Compose config valid,
`git diff --check` без вывода. Baseline до изменения:
`cd bot && uv run pytest tests/test_handlers.py -q` — `45 passed`.

Затем отдельный `product-reviewer` проверяет BR-001..BR-010 и AC-001..AC-009.
Главный оркестратор создаёт
`docs/features/product-main-menu/acceptance.md` только после этого review и
записывает `scope_revision: 1`, exact команды/результаты, BR/AC coverage и
классификацию findings. Глобальные `docs/BUSINESS.md`, `docs/ARCHITECTURE.md`,
`docs/CONTRACTS.md`, `docs/MODELS.md` не должны измениться: фича не меняет их
правила или contracts.

Далее root выполняет feature-branch commit/push/PR gates и финальное ревью exact
PR head SHA по `docs/DEVELOPMENT_WORKFLOW.md`. PR остаётся открытым. Merge и
production deploy — явные non-goals текущего Scope Contract.

## Coverage Check

| Requirement | Plan evidence |
|---|---|
| BR-001, AC-001 | PMM-001 root text, exact two-button contract |
| BR-002..BR-003, AC-002 | PMM-001 `_render_mtproxy_menu` and repeated-entry check test |
| BR-004, AC-003 | PMM-001 exact MTProxy row-order assertion |
| BR-005, AC-004 | PMM-001 root Back + PMM-002 all existing MTProxy Back targets |
| BR-006, AC-005 (menu) | PMM-003 exact two-button VPN product menu |
| BR-007, AC-005 (status/payment) | PMM-003 keeps `vpn`/status/payment path and exact regression assertions |
| BR-008, AC-006 | PMM-003 `_VPN_BACK` and `_ROOT_BACK` contract |
| BR-009, AC-007 | PMM-001 preserves consent/referrer call and changes only its destination |
| BR-010, AC-008 | PMM-001/PMM-002 callback preservation + PMM-003 VPN regression suite |
| AC-009 | Full bot, full Django, Compose and diff integration gates |

## Self-Review

- Spec coverage: BR-001..BR-010 and AC-001..AC-009 each map to at least one
  task or mandatory integration gate; no risk from `business.md` was promoted
  to a new requirement.
- Completeness scan: каждый code step содержит exact names, values и assertions;
  неопределённых соседних interfaces нет.
- Interface consistency: `product_menu -> show_mtproxy_menu/show_vpn_menu`,
  `mtproxy_menu -> show_start_screen`, MTProxy internal backs
  `-> show_mtproxy_menu`, `vpn_menu -> vpn/show_start_screen`, and VPN status
  back `-> show_vpn_menu` are consistent across all tasks and tests.
- Batch safety: no parallel work; PMM-B1 owns at most two points and PMM-B2 one;
  shared files are edited sequentially.
- Scope safety: no backend, contract, model, migration, payment, price, product
  status, dependency, unrelated refactor, merge or deploy work is planned.
