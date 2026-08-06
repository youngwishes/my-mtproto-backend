# VPN Help and Support Buttons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans` to
> execute the single assigned item through RED → GREEN. The implementer does not
> commit, push, open or update a PR, merge, or deploy.

- **Status:** approved
- **Scope revision:** 1 (immutable)
- **Route:** small local UI feature; the root agent approved the conclusion that
  no architecture change or architect review is required.

**Goal:** В существующем VPN-меню добавить отдельные URL-кнопки
инструкции и поддержки в точном порядке, не меняя существующие
действия или VPN copy.

**Approach:** Существующий `SUPPORT_URL` переиспользуется, а URL
инструкции добавляется как константа рядом с другими URL в
`messages.py`. Текущий exact-contract test сначала фиксирует пять
однокнопочных строк и поля `text`, `callback_data`, `url`, `style`, затем
`vpn_menu` получает две минимальные URL-строки.

**Tech stack:** Python 3.13, aiogram 3, pytest/pytest-asyncio, Markdown.

## Global Constraints

- Единственный источник обязательных требований — approved
  `docs/features/vpn-help-support-buttons/business.md`, `scope_revision: 1`:
  BR-001–BR-003, AC-001–AC-002.
- Порядок обязателен: test-only RED по двум отсутствующим строкам →
  минимальный production GREEN → targeted test → batch review → root
  integration verification и acceptance evidence.
- Не добавлять handlers/callbacks; не менять backend, модели/миграции,
  платежи, другие меню, VPN copy, environment/config, архитектуру,
  `apps/music/`; не делать unrelated refactor, merge или deploy.
- Бюджет feature diff: три файла production/test и один root-owned
  `acceptance.md`; новые абстракции, зависимости и конфигурация
  запрещены.

## File and Ownership Map

- `bot/tests/test_handlers.py` — implementer меняет только exact contract
  существующего `test_vpn_product_menu_uses_approved_copy_and_actions`.
- `bot/src/messages.py` — implementer добавляет только
  `VPN_SETUP_URL = "https://mtprotokeys.ru/vpn/"` рядом с URL-константами;
  `SUPPORT_URL` не меняется.
- `bot/src/keyboards.py` — implementer меняет только import
  `VPN_SETUP_URL` и список строк `vpn_menu()`.
- `docs/features/vpn-help-support-buttons/acceptance.md` — создаёт только
  root agent после batch review и интеграционной приёмки; implementer и
  batch reviewer этим файлом не владеют.

## Dependency and Batch Graph

```text
VHSB-B1 (one implementer): VHSB-001 (RED -> GREEN)
    -> read-only batch review
    -> root integration verification
    -> acceptance.md
```

Параллельной работы нет: один атомарный пункт и одна партия с
единым ownership трёх implementation-файлов.

---

### Task 1: VHSB-001 — Добавить exact URL-строки в VPN-меню

**Result:** `vpn_menu()` возвращает ровно пять однокнопочных строк:
неизменённые покупка и подписка, URL-инструкция, URL-поддержка и
неизменённый возврат — в этом точном порядке. Обе новые кнопки имеют
`callback_data is None`, `style is None` и точные URL из AC-001.

**Traceability:** BR-001–BR-003; AC-001–AC-002.

**Dependencies:** approved `business.md`, immutable `scope_revision: 1`,
утверждённое root agent заключение об отсутствии архитектурных
изменений; code dependencies отсутствуют.

**Files and ownership:** только `bot/tests/test_handlers.py`,
`bot/src/messages.py`, `bot/src/keyboards.py` в границах File and Ownership Map
выше. Любые другие файлы и участки этих файлов не назначены.

- [ ] **RED — расширить существующий exact test.** В
  `test_vpn_product_menu_uses_approved_copy_and_actions` оставить точную
  проверку `VPN_PRODUCT_MENU_TEXT`, а keyboard assertion заменить на:

  ```python
  assert [
      [
          (
              button.text,
              button.callback_data,
              button.url,
              button.style,
          )
          for button in row
      ]
      for row in markup.inline_keyboard
  ] == [
      [("💳 Купить VPN", "vpn", None, "success")],
      [("🔑 Моя подписка", "vpn_subscription", None, "primary")],
      [("📖 Как настроить", None, "https://mtprotokeys.ru/vpn/", None)],
      [("💬 Поддержка", None, "https://t.me/mtprotokeys_support", None)],
      [("🔙 Назад", "show_start_screen", None, None)],
  ]
  ```

- [ ] **Подтвердить ожидаемый RED.** Из корня репозитория:

  ```bash
  cd bot && uv run pytest \
    tests/test_handlers.py::test_vpn_product_menu_uses_approved_copy_and_actions -q
  ```

  Ожидаемый RED: exact list comparison падает, потому что actual
  keyboard содержит три строки и в нём отсутствуют строки
  `📖 Как настроить` и `💬 Поддержка`; text assertion и три
  существующие строки не должны быть причиной падения.

- [ ] **Minimal production GREEN.**

  1. В `bot/src/messages.py` рядом с URL-константами добавить:

     ```python
     VPN_SETUP_URL = "https://mtprotokeys.ru/vpn/"
     ```

  2. В `bot/src/keyboards.py` добавить `VPN_SETUP_URL` в существующий import
     из `src.messages`; `SUPPORT_URL` переиспользовать без изменения.
  3. В `vpn_menu()` после строки `🔑 Моя подписка` и до `[_ROOT_BACK]`
     вставить ровно:

     ```python
     [InlineKeyboardButton(text="📖 Как настроить", url=VPN_SETUP_URL)],
     [InlineKeyboardButton(text="💬 Поддержка", url=SUPPORT_URL)],
     ```

  Не задавать `callback_data` или `style` новым кнопкам; не менять три
  существующие строки.

- [ ] **Подтвердить targeted GREEN.** Повторить RED-команду и
  получить PASS. Exact assertion одновременно подтверждает BR-001–BR-003
  и AC-001–AC-002.

- [ ] **Documentation.** Implementer не меняет docs: approved
  `business.md` уже фиксирует всё новое поведение, а глобальные
  business/architecture/contracts/models docs не затронуты. Root agent
  создаёт `acceptance.md` только после проверок и интеграционной приёмки.

- [ ] **Проверка партии.** Из корня репозитория:

  ```bash
  cd bot && uv run pytest \
    tests/test_handlers.py::test_vpn_product_menu_uses_approved_copy_and_actions -q
  git diff --check
  ```

  Ожидаемый GREEN: targeted test PASS, `git diff --check` успешен,
  а implementer diff ограничен тремя назначенными файлами.

**Completion criterion:** targeted test зелёный; exact keyboard contract имеет
пять однокнопочных строк и все 20 значений из AC-001; обе новые кнопки
не имеют callback/style; три существующие строки и VPN text не изменены;
implementer diff соблюдает ownership и non-goals.

## Task Packet VHSB-B1

- **scope_revision:** 1 (immutable).
- **Plan item IDs:** `VHSB-001`; один implementer, один последовательный
  batch, параллельная работа запрещена.
- **Assigned requirements:** BR-001–BR-003; AC-001–AC-002.
- **Allowed/expected implementer files:** `bot/src/messages.py`,
  `bot/src/keyboards.py`, `bot/tests/test_handlers.py` только в границах
  ownership выше. `business.md` и `plan.md` read-only.
- **Expected root-only file:**
  `docs/features/vpn-help-support-buttons/acceptance.md` после batch review и
  integration acceptance; implementer и reviewer его не меняют.
- **Forbidden adjacent work:** любые другие файлы или участки трёх
  файлов; handlers/callbacks, backend, модели/миграции, платежи, другие
  меню, VPN copy, env/config, architecture, `apps/music/`, новые
  abstractions/dependencies, unrelated refactor, commit/push/PR/merge/deploy.
- **Non-goals:** любое новое поведение сверх двух URL-кнопок и
  exact ordering/values из BR/AC; изменение существующих actions/text; настройка
  URL через config/environment.
- **Dependencies:** approved revision 1, no-architecture-change conclusion;
  внутри VHSB-001 строго RED → GREEN → targeted verification; затем
  read-only batch review и root integration gates.
- **Budget:** одна URL-константа, один import, две keyboard rows,
  один расширенный existing exact test; три implementer-файла и один
  root-owned acceptance file.
- **Completion criterion:** критерий VHSB-001 выполнен, batch review не
  содержит подтверждённых `blocking_in_scope`, root checks зелёные, а
  `acceptance.md` трассирует evidence к BR-001–BR-003 и AC-001–AC-002.

## Root Integration and Acceptance Gate

После targeted GREEN implementer останавливается. Root agent запускает
отдельный read-only batch review для точного diff партии VHSB-B1,
проверяет классификацию находок и затем из корня репозитория выполняет:

```bash
cd bot && uv run pytest \
  tests/test_handlers.py::test_vpn_product_menu_uses_approved_copy_and_actions -q
cd ..
make test
docker compose -f docker-compose.yml config --quiet
git diff --check
git diff --name-only
```

Gate успешен, когда targeted bot test и `make test` зелёные, Compose config
валиден, `git diff --check` успешен, а feature diff перед созданием
acceptance ограничен `bot/src/messages.py`, `bot/src/keyboards.py`,
`bot/tests/test_handlers.py` и feature artifacts `business.md`/`plan.md`. После
интеграционной приёмки root agent создаёт
`docs/features/vpn-help-support-buttons/acceptance.md` с точными командами,
результатами и трассировкой evidence к BR/AC. Создание acceptance
не разрешает implementer-у commit/push и не включает merge/deploy.
