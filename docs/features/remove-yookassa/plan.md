# Telegram Stars-only Payments Implementation Plan

> **For agentic workers:** выполнить оба пункта одним последовательным batch
> через TDD. Один `plan-implementer` получает не более этих двух пунктов;
> commit, push, PR, merge и deploy остаются у главного оркестратора.

- **Status:** approved
- **Scope revision:** 2 (immutable)
- **Route:** small local feature. Главный агент зафиксировал, что архитектурные
  изменения и review архитектора не требуются: модели, backend API и
  взаимодействия компонентов остаются прежними.

**Goal:** новые экраны покупки MTProxy, подарочного сертификата и VPN создают
только Telegram Stars invoice, три старых callback ЮKassa безопасно завершаются
без побочных эффектов, а fulfilment ранее завершённых non-XTR платежей
сохраняется.

**Approach:** восстановить из `stash@{0}` только пользовательский Stars-only WIP
в разрешённых bot/tests/docs-файлах, причём сначала тесты и ожидаемый RED, затем
минимальный production diff и GREEN. После этого отдельным RED→GREEN циклом
добавить отсутствующие safe no-op handlers для трёх legacy callback. Backend
production code, модели, API и historical payment representation не менять.

**Tech stack:** Python 3.13, aiogram 3, pytest/pytest-asyncio, respx/httpx,
Pydantic Settings, Markdown, Docker Compose.

## Global Constraints

- Единственный источник поведения — approved
  `docs/features/remove-yookassa/business.md`, `scope_revision: 2`: BR-001..
  BR-003 и AC-001..AC-003.
- Новые MTProxy, gift и VPN экраны содержат только существующие Stars callbacks;
  цены, payloads и правила выдачи не меняются.
- `pay_yukassa`, `gift_yukassa`, `vpn_pay_yukassa` остаются зарегистрированы,
  но выполняют только `await callback.answer()`; invoice, backend call, send и
  edit запрещены.
- `process_successful_payment` продолжает выбирать `provider_payment_charge_id`
  и provider `"yukassa"` для любого non-XTR successful payment, включая
  MTProxy, gift и VPN payloads.
- `stash@{0}` — пользовательский WIP, а не новый источник требований. Из него
  нельзя восстанавливать `src/apps/core/tests/test_codex_agents.py`,
  `docs/features/remove-yookassa/business.md` или прежний черновик `plan.md`.
- Не менять backend production code, models/enums/migrations/API,
  `integration_tests/`, `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`,
  `docs/MODELS.md`, исторические feature-артефакты и `apps/music/`.
- Бюджет: один последовательный batch из двух пунктов, 18 существующих файлов,
  ноль новых implementation-файлов, ноль зависимостей/абстракций/refactor.

## File and dependency map

- Presentation: `bot/src/keyboards.py`, `bot/src/messages.py` — Stars-only copy
  и keyboards для трёх новых экранов.
- Handlers: `bot/src/handlers/payments.py`, `bot/src/handlers/vpn.py` — Stars
  issuance, неизменный successful-payment fulfilment и три legacy no-op routes.
- Bot payment client/wiring: `bot/src/domains/payments/client.py`,
  `bot/src/domains/payments/__init__.py`, `bot/src/config.py`,
  `bot/src/dependencies.py` — удалить только больше не используемое создание
  card invoices и provider token wiring; confirmation methods сохранить.
- Tests: `bot/tests/test_handlers.py`,
  `bot/tests/domains/payments/test_client.py`, `bot/tests/test_config.py`,
  `bot/tests/test_dependencies.py`, `bot/tests/conftest.py`.
- Docs: `README.md`, `bot/README.md`, `docs/BUSINESS.md`,
  `docs/apps/PAYMENTS.md`, `docs/apps/VPN.md` — новые invoices только Stars и
  совместимость fulfilment старых non-XTR payments.

```text
RYK-B1 (one implementer, sequential):
RYK-001 -> RYK-002 -> read-only batch review -> root integration verification
```

Параллельной реализации нет: пункты пересекаются в
`bot/tests/test_handlers.py`, `bot/src/handlers/payments.py` и
`bot/src/handlers/vpn.py`.

---

### RYK-001 — Восстановить и проверить Stars-only issuance и legacy fulfilment

**Result:** новые MTProxy, gift и VPN экраны показывают единственную Stars
кнопку; bot больше не строит card invoices и не требует provider token для
новых счетов; обработка завершённых non-XTR MTProxy/gift/VPN платежей остаётся
на прежних confirmation endpoints и использует provider `yukassa`.

**Traceability:** BR-001, BR-003; AC-001, AC-003.

**Dependencies:** approved `business.md`, `scope_revision: 2`; root conclusion
«architecture change not required»; доступен неизменённый `stash@{0}`. Пункт
не зависит от implementation changes.

**Files and ownership:**

- Test-first restore/modify:
  `bot/tests/test_handlers.py`, `bot/tests/domains/payments/test_client.py`,
  `bot/tests/test_config.py`, `bot/tests/test_dependencies.py`,
  `bot/tests/conftest.py` — только Stars-only expectations, удаление ожиданий
  card-invoice/config wiring и assertions сохранённого non-XTR fulfilment.
- Production:
  `bot/src/keyboards.py`, `bot/src/messages.py`,
  `bot/src/handlers/payments.py`, `bot/src/handlers/vpn.py`,
  `bot/src/domains/payments/client.py`,
  `bot/src/domains/payments/__init__.py`, `bot/src/config.py`,
  `bot/src/dependencies.py` — только пользовательский WIP по удалению нового
  ЮKassa issuance. Safe no-op handlers принадлежат RYK-002.
- Documentation: `README.md`, `bot/README.md`, `docs/BUSINESS.md`,
  `docs/apps/PAYMENTS.md`, `docs/apps/VPN.md`.

**RED test:**

- [ ] Восстановить из `stash@{0}` только пять назначенных test-файлов, не
  применяя stash целиком:

  ```bash
  git restore --source='stash@{0}' -- \
    bot/tests/conftest.py \
    bot/tests/domains/payments/test_client.py \
    bot/tests/test_config.py \
    bot/tests/test_dependencies.py \
    bot/tests/test_handlers.py
  ```

- [ ] До production-изменений усилить AC-003 в
  `test_successful_vpn_payment_routes_only_to_vpn_buy_and_shows_happ_import`:
  параметризовать `(currency, invoice_payload, expected_charge_id,
  expected_provider)` cases как `("XTR", "vpn_stars", "vpn_ch_stars",
  "stars")` и `("RUB", "vpn_yukassa", "vpn_ch_card", "yukassa")`. Сохранить
  уже восстановленные проверки regular non-XTR charge/provider и gift non-XTR
  code fulfilment.
- [ ] Запустить RED из корня:

  ```bash
  cd bot && uv run pytest tests/test_handlers.py \
    -k "payment_screen_includes_legal_links or gift_certificate_screen_shows_payment_options or vpn_purchase_fetches_stars_invoice_and_shows_stars_only_screen" -q
  ```

  Ожидаемый RED: exact keyboard assertions видят существующие callbacks
  ЮKassa, а VPN handler всё ещё запрашивает card invoice. Падение должно быть
  связано только с отсутствующим Stars-only production diff.

**Minimal production change:**

- [ ] Восстановить только восемь назначенных production-файлов из WIP:

  ```bash
  git restore --source='stash@{0}' -- \
    bot/src/config.py \
    bot/src/dependencies.py \
    bot/src/domains/payments/__init__.py \
    bot/src/domains/payments/client.py \
    bot/src/handlers/payments.py \
    bot/src/handlers/vpn.py \
    bot/src/keyboards.py \
    bot/src/messages.py
  ```

  Это удаляет ЮKassa buttons/card-invoice DTO и methods/provider-token wiring,
  оставляет существующие Stars callbacks/invoices и не изменяет
  `process_successful_payment`. Не восстанавливать никакие другие файлы из
  stash и не добавлять fallback/provider logic.

**Documentation:**

- [ ] Восстановить только пять назначенных документов из WIP:

  ```bash
  git restore --source='stash@{0}' -- \
    README.md \
    bot/README.md \
    docs/BUSINESS.md \
    docs/apps/PAYMENTS.md \
    docs/apps/VPN.md
  ```

  Документы должны описывать только новые Stars invoices, сохраняя backend
  schema/history и fulfilment ранее созданных non-XTR invoices.

**Verification:**

- [ ] Получить GREEN:

  ```bash
  cd bot && uv run pytest \
    tests/test_handlers.py \
    tests/domains/payments/test_client.py \
    tests/test_config.py \
    tests/test_dependencies.py -q
  ```

**Completion criterion:** все четыре test modules зелёные; три новых payment
экрана имеют exact Stars-only keyboards; Stars invoice tests всех продуктов
зелёные; regular, gift и VPN non-XTR tests передают provider charge ID и
`yukassa` в существующий fulfilment; diff пункта ограничен перечисленными 18
файлами. Отсутствующие после WIP legacy callback handlers пока являются
единственной незавершённой частью и немедленно закрываются зависимым RYK-002.

---

### RYK-002 — Вернуть три legacy callback как safe no-op

**Result:** `pay_yukassa`, `gift_yukassa` и `vpn_pay_yukassa` по старым
сообщениям маршрутизируются в handler, который только отвечает на callback и не
создаёт invoice, не вызывает backend, не отправляет и не редактирует сообщения.

**Traceability:** BR-002; AC-002. Техническая задача: сохранить router coverage
для трёх callback strings после Stars-only cleanup из RYK-001.

**Dependencies:** RYK-001 targeted GREEN; в восстановленном WIP три handler-а
отсутствуют, что создаёт ожидаемый RED для новых тестов.

**Files and ownership:**

- Test: `bot/tests/test_handlers.py` — только один parameterized test с тремя
  cases для legacy callbacks; не возвращать card invoice fixtures/tests.
- Production: `bot/src/handlers/payments.py` — no-op handlers для
  `pay_yukassa`, `gift_yukassa`; `bot/src/handlers/vpn.py` — no-op handler для
  `vpn_pay_yukassa`.
- Documentation: новых правок не требуется; approved feature `business.md` и
  документы RYK-001 уже фиксируют compatibility boundary.

**RED test:**

- [ ] В `bot/tests/test_handlers.py` импортировать модуль
  `src.handlers.vpn` рядом с `payments_module`, добавить `import inspect` и
  parameterized test с cases
  `(payments_module, "process_pay_yukassa", "pay_yukassa")`,
  `(payments_module, "process_gift_yukassa", "gift_yukassa")`,
  `(vpn_module, "process_vpn_pay_yukassa", "vpn_pay_yukassa")`. Для каждого
  case получить handler через `getattr`, вызвать его только с
  `FakeCallback(data=callback_data)` и проверить:

  ```python
  assert tuple(inspect.signature(handler).parameters) == ("callback",)
  assert callback.answers == [((), {})]
  assert callback.message.answers == []
  assert callback.message.edits == []
  assert fake_bot.invoices == []
  ```

  Один `FakeBot` подставить monkeypatch-ом в оба handler modules. Не создавать
  `Dependencies`/`FakePayments`: отсутствие dependency parameter является
  частью no-backend contract.
- [ ] Запустить только три cases:

  ```bash
  cd bot && uv run pytest tests/test_handlers.py \
    -k "legacy_yukassa_callbacks_are_safe_noops" -q
  ```

  Ожидаемый RED после RYK-001: три FAIL на `getattr`, потому что WIP удалил
  функции. Не ослаблять assertions и не возвращать прежние invoice tests.

**Minimal production change:**

- [ ] Добавить в прежних местах router-а ровно три функции следующей формы,
  меняя только callback string и имя функции:

  ```python
  @router.callback_query(F.data == "pay_yukassa")
  async def process_pay_yukassa(callback: CallbackQuery) -> None:
      await callback.answer()
  ```

  Для `gift_yukassa` функция находится в `handlers/payments.py`, для
  `vpn_pay_yukassa` — в `handlers/vpn.py`. Не принимать `deps`, не обращаться к
  `bot`, invoice/client/backend/message и не добавлять пользовательский текст.

**Verification:**

- [ ] Повторить RED-команду и получить `3 passed`, затем выполнить:

  ```bash
  cd bot && uv run pytest tests/test_handlers.py -q
  ```

**Completion criterion:** parameterized test имеет три зелёных case; каждая
функция зарегистрирована на исходной callback строке, принимает только
`callback`, вызывает один `callback.answer()` и не имеет других эффектов; diff
RYK-002 ограничен тремя handler-файлами (с общим ownership
`test_handlers.py`).

## Task Packet RYK-B1

- **scope_revision:** 2 (immutable).
- **Plan item IDs:** `RYK-001`, затем `RYK-002`; один implementer, максимум два
  пункта, только последовательное выполнение.
- **Assigned BR/AC:** RYK-001 — BR-001, BR-003; AC-001, AC-003. RYK-002 —
  BR-002; AC-002.
- **Allowed and expected files:** `README.md`, `bot/README.md`,
  `bot/src/config.py`, `bot/src/dependencies.py`,
  `bot/src/domains/payments/__init__.py`,
  `bot/src/domains/payments/client.py`, `bot/src/handlers/payments.py`,
  `bot/src/handlers/vpn.py`, `bot/src/keyboards.py`, `bot/src/messages.py`,
  `bot/tests/conftest.py`, `bot/tests/domains/payments/test_client.py`,
  `bot/tests/test_config.py`, `bot/tests/test_dependencies.py`,
  `bot/tests/test_handlers.py`, `docs/BUSINESS.md`,
  `docs/apps/PAYMENTS.md`, `docs/apps/VPN.md`.
- **Ownership boundary:** только новые bot payment screens/issuance/wiring,
  соответствующие bot tests, сохранённый successful-payment routing, три
  legacy no-op handlers и назначенная documentation. `business.md` и этот
  `plan.md` принадлежат product/planner/root и implementer-ом не меняются.
- **Forbidden adjacent work:** восстановление stash целиком; изменение
  `src/apps/core/tests/test_codex_agents.py`; любые другие файлы; backend
  production/tests, model/enum/migration/API/contract; old invoice cancellation;
  price/fulfilment changes; integration/e2e cleanup; abstractions/refactor/new
  dependencies; historical feature docs; `apps/music/`; commit/push/PR/merge/
  deploy.
- **Non-goals:** удаление ЮKassa из backend или historical data, обработка
  незавершённых старых invoices, новая ошибка/уведомление для legacy buttons,
  изменение Stars payloads, prices или выдачи услуг.
- **Dependencies:** approved revision 2 и no-architecture-change conclusion;
  `stash@{0}` используется только перечисленными pathspecs; RYK-002 начинается
  после targeted GREEN RYK-001.
- **Budget:** 18 существующих файлов, ноль новых implementation files; один
  selective WIP restore, один дополнительный VPN non-XTR test case, один
  parameterized no-op test из трёх cases и три двухстрочных handler bodies.
- **Completion criterion:** оба item criteria и root checks ниже зелёные;
  итоговый tracked diff содержит только allowed files; запрещённый revert-test
  и backend production diff отсутствуют.

## Root integration verification

После реализации и read-only batch review главный оркестратор выполняет из
корня репозитория:

```bash
(cd bot && uv run pytest \
  tests/test_handlers.py \
  tests/domains/payments/test_client.py \
  tests/test_config.py \
  tests/test_dependencies.py -q)
(cd bot && uv run pytest)
make test
docker compose -f docker-compose.yml config --quiet
git diff --check
git diff --exit-code -- \
  src/apps/core/tests/test_codex_agents.py \
  src/apps integration_tests \
  docs/ARCHITECTURE.md docs/CONTRACTS.md docs/MODELS.md
git diff --name-only
git status --short
```

Итоговый `git diff --name-only` должен быть подмножеством 18 allowed files из
`RYK-B1`; отдельно созданные root-ом `business.md` и `plan.md` допустимы в
`git status`, но implementer их не редактирует. Полный bot suite и `make test`
зелёные, Compose config валиден, forbidden paths не имеют diff, а итоговая
трассировка BR/AC полна.
