# Admin Payment Method Toggles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Every
> implementation item follows RED -> minimal GREEN -> refactor/verification.
> Implementers do not commit, push, open/update a PR, merge, or deploy.

- **Status:** approved
- **Scope revision:** 2 (immutable)
- **Architecture:** approved in
  `docs/features/admin-payment-method-toggles/architecture.md`
- **Plan review:** two confirmed workflow findings are addressed in this
  revision; architect re-review is still required before root approval.
- **Route:** ordinary product feature; implementation may start only after the
  architect reviews this plan and the root agent marks it approved.

**Goal:** Дать Django-администратору два глобальных переключателя Telegram
Stars и Crypto Pay и применять их без рестарта при каждом новом открытии
экранов оплаты MTProxy, VPN и подарочного сертификата, сохранив текущие кнопки
и порядок сразу после миграции.

**Architecture:** `PaymentMethod` в `apps.payments` хранит одну глобальную
активность на allowlisted provider code. Существующие product GET endpoints на
каждом запросе получают упорядоченные активные коды selector-ом и добавляют
`payment_methods` в ответ; bot переносит поле в `StarsInvoice` и фильтрует три
существующие клавиатуры, не меняя callbacks или payment flows.

**Tech Stack:** Python 3.13, Django 6, Django REST Framework, SQLite, Django
admin, aiogram 3, `unittest`/pytest, `httpx` + `respx`, Docker Compose, Markdown.

## Global Constraints

- Единственный источник обязательного поведения — approved
  `docs/features/admin-payment-method-toggles/business.md`,
  `scope_revision: 2`: BR-001–BR-006, AC-001–AC-008 и их non-goals.
- Реализация следует только approved `architecture.md`: новая модель в
  `apps.payments`, существующие product endpoints, существующий bot payment
  client и три существующие keyboard/handler flows; новый endpoint, app,
  service, task, exception, cache или provider framework запрещены.
- БД — source of truth. Каждый новый экран выполняет существующий product GET;
  ни backend, ни bot не кешируют `payment_methods`.
- Поддержанные codes и фиксированный порядок: `stars`, затем `crypto_pay`.
  Admin меняет только `is_active`; code, label и order не редактируются.
- `PaymentMethod` наследует `BaseDjangoModel`; собственное поле только
  `code = CharField(max_length=32, unique=True)` с choices Telegram Stars и
  Crypto Pay; связей с `Product` и per-product полей нет.
- Data migration создаёт отсутствующие `stars` и `crypto_pay` через
  `get_or_create(defaults={"is_active": True})`; повторный seed не включает
  обратно существующую выключенную строку.
- API-поле аддитивно и всегда присутствует как упорядоченный JSON array.
  Существующие response fields, `ProductNotFound` и `Bot-Auth-Token` не
  меняются.
- При пустом списке точный текст — `Оплата временно недоступна`; payment
  callbacks отсутствуют, текущая кнопка «Назад» остаётся.
- Старые `pay_*`, `vpn_pay_*`, `gift_*`, invoice payload, prices, fulfilment и
  purchase result flows не меняются и не получают повторную runtime-проверку
  активности.
- Исторический `docs/features/cryptopay-all-products/` не изменяется.
  `apps/music`, `apps/notifications`, provider credentials/settings, env,
  deploy и production не входят в работу.
- Один `plan-implementer` получает не более двух plan IDs. Здесь каждая
  implementation-партия содержит один ID; партии выполняются последовательно,
  после каждой root запускает отдельный read-only batch review.
- После product acceptance только root фиксирует scoped commit(s), публикует
  feature branch/PR и координирует финальное ревью точного remote PR head.
  Implementer и product-reviewer не выполняют commit, push или PR mutation.
- Merge и production deploy не входят в этот план даже после одобренного
  финального PR review; для них нужны последующие отдельные разрешения.

---

## Complete File Map and Responsibilities

### Backend storage, admin and read contract

- `src/apps/payments/models.py` — `PaymentMethod` с единственным собственным
  полем `code` и inherited global `is_active`.
- `src/apps/payments/migrations/0008_payment_method.py` — additive schema и
  idempotent seed двух активных поддержанных строк.
- `src/apps/payments/selectors.py` — allowlisted active codes в порядке
  Stars -> Crypto Pay.
- `src/apps/payments/admin.py` — change-only admin: редактируется только
  `is_active`, add/delete/actions отключены.
- `src/apps/payments/api/v1/serializers/get_product_serializer.py` — additive
  `payment_methods` из serializer context без ORM.
- `src/apps/payments/api/v1/views/get_product_view.py` — selector вызывается на
  каждом GET и его tuple передаётся serializer-у.

### Bot contract and three screens

- `bot/src/domains/payments/client.py` — `StarsInvoice.payment_methods` и exact
  tuple mapping из product JSON.
- `bot/src/keyboards.py` — три builders фильтруют только известные buttons и
  всегда сохраняют фиксированный порядок и Back.
- `bot/src/handlers/payments.py` — MTProxy/renewal и gift получают product перед
  rendering; empty tuple даёт точный zero-state.
- `bot/src/handlers/vpn.py` — существующий VPN product GET одновременно даёт
  price и availability; empty tuple даёт тот же zero-state.

### Tests, global documentation and acceptance

- `src/apps/payments/tests/test_models.py`, `test_selectors.py`,
  `test_payment_method_admin.py`, `test_payment_method_migration.py` — model,
  selector, admin и seed contracts.
- `src/apps/payments/tests/test_views/test_get_product_view.py` — обе routes,
  матрица, sequential GET и auth/product regressions.
- `bot/tests/domains/payments/test_client.py` — JSON list -> immutable tuple.
- `bot/tests/test_handlers.py` — PMT-004 сначала обновляет все существующие
  `StarsInvoice` fixtures новым обязательным полем, затем PMT-005 добавляет
  полную матрицу `3 screens x 4 states`, refresh calls, Back и unchanged
  callback/payment regressions.
- `docs/BUSINESS.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`,
  `docs/MODELS.md`, `docs/apps/PAYMENTS.md` — актуальные глобальные правила,
  data flow, API field, model/admin и operational semantics.
- `docs/features/admin-payment-method-toggles/acceptance.md` — создаёт только
  product-reviewer после зелёных integration gates; implementers и batch
  reviewers им не владеют.

### Root publication and final review

- PMT-008 не создаёт новый repository artifact: root проверяет полный feature
  path set, фиксирует только scoped changes, push-ит текущую feature branch и
  открывает PR в `main` через GitHub CLI.
- PMT-009 выполняет новый read-only `code-reviewer` точного remote PR head;
  единственная разрешённая reviewer mutation — структурированный
  `gh pr review --comment`. Root проверяет comment verdict, checks и неизменный
  head SHA; PR остаётся открытым.

## Fixed Interfaces Across Tasks

Эти имена, типы и keyword arguments являются частью плана и не меняются между
партиями:

```python
class PaymentMethod(BaseDjangoModel):
    code = models.CharField(
        "код",
        max_length=32,
        unique=True,
        choices=(
            (PaymentProviderEnum.STARS, "Telegram Stars"),
            (PaymentProviderEnum.CRYPTO_PAY, "Crypto Pay"),
        ),
    )


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class StarsInvoice:
    title: str
    description: str
    prices: list[LabeledPrice]
    payment_methods: tuple[str, ...]
    currency: str = "XTR"
    provider_token: str = ""
```

Exact callable signatures:

- `seed_payment_methods(apps, schema_editor) -> None`;
- `get_active_payment_method_codes() -> tuple[str, ...]`;
- `payment_methods(*, payment_methods: tuple[str, ...]) -> InlineKeyboardMarkup`;
- `vpn_payment_methods(*, stars_price: int, payment_methods: tuple[str, ...]) -> InlineKeyboardMarkup`;
- `gift_certificate_payment_methods(*, payment_methods: tuple[str, ...]) -> InlineKeyboardMarkup`.

`GetProductSerializer` получает context exact shape
`{"payment_methods": tuple[str, ...]}`. Product JSON получает exact field
`"payment_methods": list[str]`. Никакой другой DTO, endpoint или config key не
вводится.

## Dependency and Batch Graph

```text
PMT-B1 / PMT-001  model + migration + selector
        |
PMT-B2 / PMT-002  constrained admin
        |
PMT-B3 / PMT-003  additive product API field
        |
PMT-B4 / PMT-004  bot DTO mapping
        |
PMT-B5 / PMT-005  three payment screens
        |
PMT-B6 / PMT-006  root docs + integration verification
        |
PMT-B7 / PMT-007  product-reviewer acceptance evidence
        |
PMT-B8 / PMT-008  root scoped commit + push + PR
        |
PMT-B9 / PMT-009  fresh final review of exact PR head
```

Параллельных партий нет. Каждая следующая партия использует точный interface и
GREEN evidence предыдущей; последовательность также исключает одновременный
write и read-only review в общем рабочем дереве.

---

### Task 1: PMT-001 — Persist and select supported global payment methods

**Result:** backend хранит единственную глобальную активность каждой
поддержанной строки; migration создаёт обе строки активными без перезаписи
сохранённого `False`; selector возвращает только active allowlisted codes в
порядке Stars -> Crypto Pay.

**Traceability:** BR-001, BR-002, BR-005, BR-006; AC-001, AC-003, AC-005,
AC-007.

**Dependencies:** approved revision 2 artifacts; code dependencies отсутствуют.

**Files and ownership:** modify `src/apps/payments/models.py`,
`src/apps/payments/selectors.py`, `src/apps/payments/tests/test_models.py`,
`src/apps/payments/tests/test_selectors.py`; create
`src/apps/payments/migrations/0008_payment_method.py` and
`src/apps/payments/tests/test_payment_method_migration.py`. Другие файлы и
соседние payment models/selectors не назначены.

- [ ] **RED — зафиксировать model, seed и selector contracts.** Добавить
  `TestPaymentMethodModel`, `TestActivePaymentMethodCodes` и
  `TestPaymentMethodMigration`. Selector matrix должна физически создавать
  Crypto Pay раньше Stars и проверять four states плюс unknown code:

  ```python
  class TestActivePaymentMethodCodes(TestCase):
      def setUp(self) -> None:
          PaymentMethod.objects.all().delete()
          self.crypto = PaymentMethod.objects.create(code="crypto_pay")
          self.stars = PaymentMethod.objects.create(code="stars")

      def test_returns_only_active_supported_codes_in_fixed_order(self) -> None:
          states = (
              (("stars", "crypto_pay"), ("stars", "crypto_pay")),
              (("stars",), ("stars",)),
              (("crypto_pay",), ("crypto_pay",)),
              ((), ()),
          )
          for active_codes, expected in states:
              with self.subTest(active_codes=active_codes):
                  PaymentMethod.objects.all().update(is_active=False)
                  PaymentMethod.objects.filter(code__in=active_codes).update(
                      is_active=True
                  )
                  self.assertEqual(get_active_payment_method_codes(), expected)

      def test_excludes_unknown_active_code(self) -> None:
          PaymentMethod.objects.create(code="unknown")
          self.assertEqual(
              get_active_payment_method_codes(), ("stars", "crypto_pay")
          )
  ```

  Model test asserts unique `code`, exact two choices, inherited
  `is_active/created_at/updated_at`, and absence of any relation to `Product`.
  Migration test migrates `0007_crypto_payment_intent` ->
  `0008_payment_method`, asserts two active rows, sets `crypto_pay=False`, calls
  exported `seed_payment_methods(self.apps, None)` again, and asserts two rows
  remain with Crypto Pay still inactive.

- [ ] **Run RED and verify the reason.** From repository root:

  ```bash
  make test ARGS="apps.payments.tests.test_models.TestPaymentMethodModel apps.payments.tests.test_selectors.TestActivePaymentMethodCodes apps.payments.tests.test_payment_method_migration"
  ```

  Expected RED: imports fail because `PaymentMethod`, migration `0008` and
  `get_active_payment_method_codes` do not exist; no existing payment test is
  the source of failure.

- [ ] **Minimal production GREEN — add model and migration.** Add the exact
  `PaymentMethod` signature from Fixed Interfaces to `models.py`. Create
  `0008_payment_method.py` with `CreateModel` matching that model and:

  ```python
  SUPPORTED_PAYMENT_METHODS = ("stars", "crypto_pay")


  def seed_payment_methods(apps, schema_editor) -> None:
      payment_method = apps.get_model("payments", "PaymentMethod")
      for code in SUPPORTED_PAYMENT_METHODS:
          payment_method.objects.get_or_create(
              code=code,
              defaults={"is_active": True},
          )


  operations = [
      migrations.CreateModel(
          name="PaymentMethod",
          fields=[
              (
                  "id",
                  models.BigAutoField(
                      auto_created=True,
                      primary_key=True,
                      serialize=False,
                      verbose_name="ID",
                  ),
              ),
              (
                  "is_active",
                  models.BooleanField(default=True, verbose_name="активность"),
              ),
              (
                  "created_at",
                  models.DateTimeField(
                      auto_now_add=True,
                      null=True,
                      verbose_name="дата создания",
                  ),
              ),
              (
                  "updated_at",
                  models.DateTimeField(
                      auto_now=True,
                      null=True,
                      verbose_name="дата обновления",
                  ),
              ),
              (
                  "code",
                  models.CharField(
                      choices=[
                          ("stars", "Telegram Stars"),
                          ("crypto_pay", "Crypto Pay"),
                      ],
                      max_length=32,
                      unique=True,
                      verbose_name="код",
                  ),
              ),
          ],
      ),
      migrations.RunPython(seed_payment_methods, migrations.RunPython.noop),
  ]
  ```

  The actual `CreateModel` fields must exactly mirror `BaseDjangoModel` plus
  `code`; migration dependency is `("payments", "0007_crypto_payment_intent")`.

- [ ] **Minimal production GREEN — add ordered selector.** Reuse
  `PaymentMethod.objects.active()` and Django expressions; do not query inside
  a service or serializer:

  ```python
  _SUPPORTED_PAYMENT_METHOD_CODES = (
      PaymentProviderEnum.STARS,
      PaymentProviderEnum.CRYPTO_PAY,
  )


  def get_active_payment_method_codes() -> tuple[str, ...]:
      order = Case(
          When(code=PaymentProviderEnum.STARS, then=0),
          When(code=PaymentProviderEnum.CRYPTO_PAY, then=1),
          output_field=IntegerField(),
      )
      return tuple(
          PaymentMethod.objects.active()
          .filter(code__in=_SUPPORTED_PAYMENT_METHOD_CODES)
          .order_by(order)
          .values_list("code", flat=True)
      )
  ```

- [ ] **Targeted GREEN and refactor gate.** Repeat the RED command, then run:

  ```bash
  make test ARGS="apps.payments.tests.test_models apps.payments.tests.test_selectors apps.payments.tests.test_payment_method_migration"
  cd src && python manage.py makemigrations --settings=config.test_settings --check --dry-run
  ```

  Expected: all targeted tests PASS and Django reports `No changes detected`.
  Refactor only duplicate test setup; do not introduce a factory, service,
  cache or new enum.

- [ ] **Documentation and diff check.** Production docstrings/verbose names in
  the six assigned files are sufficient for this batch; global docs are owned
  by PMT-006. Run `git diff --check` and confirm this batch changes only its six
  owned paths.

**Completion criterion:** exact two choices and one global boolean per row;
unique code; four selector states and unknown filtering GREEN; migration seed
is active-by-default and non-overwriting on repeat; no Product relation or
per-product field; migration drift check GREEN.

#### Task Packet PMT-B1

- **scope_revision:** 2 (immutable).
- **Plan IDs:** `PMT-001`; one implementer, one sequential batch.
- **Allowed/expected files:** the six paths listed in PMT-001 only.
- **Forbidden adjacent work:** API/admin/bot/docs, existing payment/crypto/gift
  behavior, factories, services/tasks/exceptions, new enum/app/dependency/cache.
- **Non-goals:** per-product state, editable label/order, arbitrary provider
  framework, credentials, new provider, old-button runtime enforcement.
- **Dependencies:** approved artifacts only; strict RED -> GREEN -> review.
- **Budget:** at most 6 files and 360 changed lines.
- **Done:** PMT-001 completion criterion plus independent batch review with no
  confirmed `blocking_in_scope`.

---

### Task 2: PMT-002 — Expose only safe global toggles in Django admin

**Result:** Django admin lists both supported rows and permits changing only
`is_active`; code/add/delete/actions are unavailable.

**Traceability:** BR-001, BR-002, BR-005; AC-001, AC-003, AC-007.

**Dependencies:** PMT-001 GREEN and batch-approved `PaymentMethod`.

**Files and ownership:** modify `src/apps/payments/admin.py`; create
`src/apps/payments/tests/test_payment_method_admin.py`. Existing admin classes
and tests are read-only.

- [ ] **RED — add exact admin surface test.** Instantiate the admin with
  `admin.site` and assert:

  ```python
  model_admin = PaymentMethodAdmin(PaymentMethod, admin.site)
  request = RequestFactory().get("/admin/payments/paymentmethod/")

  self.assertEqual(model_admin.list_display, ("code", "is_active", "updated_at"))
  self.assertEqual(model_admin.list_editable, ("is_active",))
  self.assertEqual(
      model_admin.readonly_fields,
      ("code", "created_at", "updated_at"),
  )
  self.assertFalse(model_admin.has_add_permission(request))
  self.assertFalse(model_admin.has_delete_permission(request))
  self.assertIsNone(model_admin.actions)
  self.assertIs(admin.site._registry[PaymentMethod].__class__, PaymentMethodAdmin)
  ```

- [ ] **Run RED.**

  ```bash
  make test ARGS="apps.payments.tests.test_payment_method_admin"
  ```

  Expected RED: `PaymentMethodAdmin` cannot be imported/registered.

- [ ] **Minimal production GREEN.** Register only this model with:

  ```python
  @admin.register(PaymentMethod)
  class PaymentMethodAdmin(admin.ModelAdmin):
      actions = None
      list_display = ("code", "is_active", "updated_at")
      list_editable = ("is_active",)
      readonly_fields = ("code", "created_at", "updated_at")

      def has_add_permission(self, request: HttpRequest) -> bool:
          return False

      def has_delete_permission(
          self, request: HttpRequest, obj: object | None = None
      ) -> bool:
          return False
  ```

  Do not override `has_change_permission`: changing existing `is_active` is the
  intended admin action.

- [ ] **Targeted GREEN, refactor and documentation.** Repeat the RED command,
  then run `make test ARGS="apps.payments.tests.test_crypto_admin apps.payments.tests.test_payment_method_admin"`.
  Keep tuple attributes exact and do not alter other admin registrations.
  Global admin semantics are documented in PMT-006.

- [ ] **Diff check.** Run `git diff --check`; batch diff is limited to the two
  assigned files.

**Completion criterion:** exact admin test and existing crypto admin regression
PASS; only `is_active` is editable; add/delete/actions/code editing are absent.

#### Task Packet PMT-B2

- **scope_revision:** 2; **Plan IDs:** `PMT-002`.
- **Allowed/expected files:** `src/apps/payments/admin.py`,
  `src/apps/payments/tests/test_payment_method_admin.py` only.
- **Forbidden adjacent work:** model/migration/selector/API/bot/docs and any
  change to existing Product/Payment/Gift/Crypto admin.
- **Non-goals:** admin create/delete/rename/order, bulk actions, credentials.
- **Dependencies:** reviewed PMT-B1; strict RED -> GREEN -> review.
- **Budget:** at most 2 files and 150 changed lines.
- **Done:** PMT-002 completion criterion and batch review without confirmed
  `blocking_in_scope`.

---

### Task 3: PMT-003 — Add live payment methods to existing product responses

**Result:** both existing product routes return the same current ordered list
on every GET; no endpoint or existing response/error/auth behavior changes.

**Traceability:** BR-001, BR-003, BR-006; AC-002–AC-006.

**Dependencies:** PMT-001 selector and PMT-002 admin are GREEN/reviewed.

**Files and ownership:** modify
`src/apps/payments/api/v1/serializers/get_product_serializer.py`,
`src/apps/payments/api/v1/views/get_product_view.py`,
`src/apps/payments/tests/test_views/test_get_product_view.py` only.

- [ ] **RED — extend API setup and exact matrix.** In `setUp`, create Stars and
  Crypto Pay explicitly so tests do not depend on migration seed after flush.
  Add a helper that uses the existing auth header, then cover both routes:

  ```python
  self.stars = PaymentMethod.objects.create(code="stars")
  self.crypto = PaymentMethod.objects.create(code="crypto_pay")

  routes = (
      self.url,
      reverse("product-by-code", kwargs={"code": ProductCodeEnum.VPN_30D}),
  )
  states = (
      (("stars", "crypto_pay"), ["stars", "crypto_pay"]),
      (("stars",), ["stars"]),
      (("crypto_pay",), ["crypto_pay"]),
      ((), []),
  )
  for active_codes, expected in states:
      PaymentMethod.objects.all().update(is_active=False)
      PaymentMethod.objects.filter(code__in=active_codes).update(is_active=True)
      for route in routes:
          with self.subTest(route=route, active_codes=active_codes):
              response = self.client.get(
                  route,
                  headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
              )
              self.assertEqual(response.status_code, status.HTTP_200_OK)
              self.assertEqual(response.json()["payment_methods"], expected)
  ```

  Update the legacy exact response assertion with
  `"payment_methods": ["stars", "crypto_pay"]`. Add a sequential GET test:
  first response contains both; after `self.crypto.is_active=False` + save,
  second response contains only Stars. Keep the inactive-product error test and
  add/retain unauthenticated GET returning 403.

- [ ] **Run RED.**

  ```bash
  make test ARGS="apps.payments.tests.test_views.test_get_product_view"
  ```

  Expected RED: successful responses lack `payment_methods`; existing product
  and auth semantics remain otherwise green.

- [ ] **Minimal production GREEN — serializer context.** Add no ORM to the
  serializer:

  ```python
  class GetProductSerializer(serializers.Serializer):
      payment_methods = serializers.SerializerMethodField()

      def get_payment_methods(self, obj: object) -> tuple[str, ...]:
          return tuple(self.context["payment_methods"])
  ```

  Preserve every existing field unchanged.

- [ ] **Minimal production GREEN — request-time selector.** In
  `ProductAPIView.get`, after the existing active product lookup:

  ```python
  payment_methods = get_active_payment_method_codes()
  serializer = GetProductSerializer(
      instance=product,
      context={"payment_methods": payment_methods},
  )
  ```

  Import the selector beside `get_active_product_by_code`; do not add caching,
  endpoint branching or product-specific filtering.

- [ ] **Targeted GREEN and regression.** Repeat the RED command, then run:

  ```bash
  make test ARGS="apps.payments.tests.test_views.test_get_product_view apps.payments.tests.test_selectors"
  ```

  Expected: exact response, `2 routes x 4 states`, sequential refresh,
  inactive product and auth tests all PASS.

- [ ] **Documentation and diff check.** Serializer method typing is the only
  local documentation needed; global contract is PMT-006. Run
  `git diff --check`; diff is limited to three owned files.

**Completion criterion:** both routes always include the ordered list; a DB
toggle is visible on the next GET in the same process; old fields,
`ProductNotFound` and `Bot-Auth-Token` tests remain GREEN.

#### Task Packet PMT-B3

- **scope_revision:** 2; **Plan IDs:** `PMT-003`.
- **Allowed/expected files:** exact three PMT-003 files.
- **Forbidden adjacent work:** new endpoint, model/admin/selector changes,
  serializer ORM, per-product rules, bot/docs, existing error/auth changes.
- **Non-goals:** caching, independent config request, purchase-kind filtering.
- **Dependencies:** reviewed PMT-B1 and PMT-B2.
- **Budget:** at most 3 files and 260 changed lines.
- **Done:** PMT-003 completion criterion and batch review without confirmed
  `blocking_in_scope`.

---

### Task 4: PMT-004 — Map the additive API field into the bot invoice DTO

**Result:** both MTProxy and VPN product reads preserve the backend list as an
immutable `tuple[str, ...]` on existing `StarsInvoice`.

**Traceability:** BR-001, BR-003, BR-006; AC-002–AC-006.

**Dependencies:** PMT-003 exact API field reviewed and GREEN.

**Files and ownership:** modify `bot/src/domains/payments/client.py`,
`bot/tests/domains/payments/test_client.py` and only the existing
`StarsInvoice` fixture constructors in `bot/tests/test_handlers.py`.
Package exports do not change because `StarsInvoice` is already exported.

- [ ] **RED — add field to both product fixtures/assertions.** Extend
  `PRODUCT_JSON` and VPN response with the exact arrays; assert tuple mapping:

  ```python
  PRODUCT_JSON = {
      "title": "MTPRoto на месяц",
      "description": "Безлимитный прокси",
      "currency": "RUB",
      "provider_data": {"receipt": {"items": []}},
      "send_email_to_provider": False,
      "need_email": False,
      "price": 9900,
      "stars_price": 99,
      "payment_methods": ["stars", "crypto_pay"],
  }

  assert invoice.payment_methods == ("stars", "crypto_pay")
  assert isinstance(invoice.payment_methods, tuple)
  ```

  In the VPN test use `"payment_methods": ["crypto_pay"]` and assert
  `invoice.payment_methods == ("crypto_pay",)`. Add
  `payment_methods=("stars", "crypto_pay")` to every pre-existing
  `StarsInvoice` constructor in `bot/tests/test_handlers.py`; do not change its
  assertions or handler behavior in this batch.

- [ ] **Run RED.**

  ```bash
  cd bot && uv run pytest tests/domains/payments/test_client.py \
    -k "get_stars_invoice or get_vpn_stars_invoice" -q
  ```

  Expected RED: `StarsInvoice` has no `payment_methods` attribute/constructor
  field.

- [ ] **Minimal production GREEN.** Add the exact fixed-interface field and
  map without fallback or extra request:

  ```python
  return StarsInvoice(
      title=data["title"],
      description=data["description"],
      prices=[LabeledPrice(label=data["title"], amount=data["stars_price"])],
      payment_methods=tuple(str(code) for code in data["payment_methods"]),
  )
  ```

- [ ] **Targeted GREEN and refactor.** Repeat RED command, then run:

  ```bash
  cd bot && uv run pytest tests/domains/payments/test_client.py \
    tests/test_handlers.py -q
  ```

  Keep the existing two GET paths and all invoice fields exact; do not
  introduce a new DTO/client/config value. The handler suite must remain GREEN
  from fixture-only compatibility edits.

- [ ] **Documentation and diff check.** Type annotation documents the local
  field; global API/bot data flow belongs to PMT-006. Run `git diff --check` and
  confirm three-file ownership.

**Completion criterion:** client and unchanged handler suites GREEN; both
existing GET methods map the exact JSON array to a tuple without another
network call or fallback; handler-test edits only supply the required field.

#### Task Packet PMT-B4

- **scope_revision:** 2; **Plan IDs:** `PMT-004`.
- **Allowed/expected files:** the three PMT-004 files/scopes above only.
- **Forbidden adjacent work:** handlers/keyboards/backend/docs, new client/DTO,
  HTTP path, fallback/cache, invoice/crypto creation behavior.
- **Non-goals:** provider registry or checking activity during old callbacks.
- **Dependencies:** reviewed PMT-B3.
- **Budget:** at most 3 files and 150 changed lines.
- **Done:** PMT-004 completion criterion and batch review without confirmed
  `blocking_in_scope`.

---

### Task 5: PMT-005 — Apply one visibility matrix to all three bot screens

**Result:** MTProxy/renewal, VPN and gift screens each fetch current product
data, show known active methods in Stars -> Crypto order, or show the exact
zero-state with only the existing Back button.

**Traceability:** BR-001, BR-003, BR-004, BR-006; AC-002–AC-006, AC-008.

**Dependencies:** PMT-004 `StarsInvoice.payment_methods` reviewed and GREEN.

**Files and ownership:** modify `bot/src/keyboards.py`,
`bot/src/handlers/payments.py`, `bot/src/handlers/vpn.py`,
`bot/tests/test_handlers.py` only. Payment callback bodies, successful-payment
routing and bot messages outside the three opening handlers are read-only.

- [ ] **RED — update fakes/signatures and add the `3 x 4` screen matrix.** Make
  `FakePayments` count MTProxy product reads as well as VPN reads. Parameterize
  the three opening handlers with a `StarsInvoice` whose
  `payment_methods=methods` and exact expected callback rows:

  ```python
  SCREEN_CASES = {
      "mtproxy": (
          process_boost_paid,
          PAYMENT_METHODS_TEXT,
          {"stars": "pay_stars", "crypto_pay": "pay_crypto"},
          "show_mtproxy_menu",
      ),
      "vpn": (
          process_vpn,
          VPN_MENU_TEXT,
          {"stars": "vpn_pay_stars", "crypto_pay": "vpn_pay_crypto"},
          "show_vpn_menu",
      ),
      "gift": (
          process_gift_certificate,
          GIFT_CERTIFICATE_TEXT,
          {"stars": "gift_stars", "crypto_pay": "gift_crypto"},
          "show_mtproxy_menu",
      ),
  }


  @pytest.mark.parametrize("screen", tuple(SCREEN_CASES))
  @pytest.mark.parametrize(
      "methods",
      (
          ("stars", "crypto_pay"),
          ("stars",),
          ("crypto_pay",),
          (),
      ),
  )
  async def test_payment_method_screen_matrix(screen, methods) -> None:
      handler, normal_text, callback_by_method, back_callback = SCREEN_CASES[screen]
      invoice = StarsInvoice(
          title="Товар",
          description="Описание",
          prices=[LabeledPrice(label="Товар", amount=149)],
          payment_methods=methods,
      )
      payments = FakePayments(stars=invoice)
      callback = FakeCallback(chat_id=42, user_id=42)
      if screen == "vpn":
          deps = _deps_with_vpn(
              vpn=FakeVPN(
                  menu=VPNMenu(
                      status="none",
                      expired_at=None,
                      subscription_url=None,
                  )
              ),
              payments=payments,
          )
      else:
          deps = make_deps(payments=payments)

      await handler(callback, deps)

      text, markup = callback.message.edits[0]
      expected_payment_callbacks = [
          callback_by_method[code]
          for code in ("stars", "crypto_pay")
          if code in methods
      ]
      actual_callbacks = [
          row[0].callback_data for row in markup.inline_keyboard
      ]
      assert actual_callbacks == [*expected_payment_callbacks, back_callback]
      assert text == (
          normal_text if methods else "Оплата временно недоступна"
      )
      assert payments.stars_invoice_calls == (0 if screen == "vpn" else 1)
      assert payments.vpn_stars_invoice_calls == (1 if screen == "vpn" else 0)
  ```

  Import `PAYMENT_METHODS_TEXT` and `GIFT_CERTIFICATE_TEXT` beside existing
  message constants. Update direct keyboard tests to pass `payment_methods=`
  and add an unknown-code assertion proving it creates no callback; its markup
  must contain only the relevant Back row.

- [ ] **Run RED.**

  ```bash
  (cd bot && uv run pytest \
    tests/test_handlers.py::test_payment_method_screen_matrix -q)
  ```

  Expected selection: exactly 12 parametrized cases (`3 screens x 4 method
  states`). Expected RED: all selected matrix cases reach the new contract and
  fail because builder signatures do not accept the field, MTProxy/gift do not
  fetch product data, or empty states still render payment buttons. A zero-test
  selection or fewer than 12 collected matrix cases is not an acceptable RED.

- [ ] **Minimal production GREEN — filter builders in fixed order.** Replace
  the three existing builders with these exact bodies; the set is used only
  for membership and cannot alter output order:

  ```python
  def payment_methods(
      *, payment_methods: tuple[str, ...]
  ) -> InlineKeyboardMarkup:
      active = set(payment_methods)
      keyboard: list[list[InlineKeyboardButton]] = []
      if "stars" in active:
          keyboard.append(
              [
                  InlineKeyboardButton(
                      text="⭐ Telegram Stars — 99 ★",
                      callback_data="pay_stars",
                      style="primary",
                  )
              ]
          )
      if "crypto_pay" in active:
          keyboard.append(
              [InlineKeyboardButton(text=CRYPTO_PAY_BUTTON, callback_data="pay_crypto")]
          )
      keyboard.append([_MTPROXY_BACK])
      return InlineKeyboardMarkup(inline_keyboard=keyboard)


  def vpn_payment_methods(
      *, stars_price: int, payment_methods: tuple[str, ...]
  ) -> InlineKeyboardMarkup:
      active = set(payment_methods)
      keyboard: list[list[InlineKeyboardButton]] = []
      if "stars" in active:
          keyboard.append(
              [
                  InlineKeyboardButton(
                      text=f"⭐ Telegram Stars — {stars_price} ★",
                      callback_data="vpn_pay_stars",
                      style="primary",
                  )
              ]
          )
      if "crypto_pay" in active:
          keyboard.append(
              [
                  InlineKeyboardButton(
                      text=CRYPTO_PAY_BUTTON,
                      callback_data="vpn_pay_crypto",
                  )
              ]
          )
      keyboard.append([_VPN_BACK])
      return InlineKeyboardMarkup(inline_keyboard=keyboard)


  def gift_certificate_payment_methods(
      *, payment_methods: tuple[str, ...]
  ) -> InlineKeyboardMarkup:
      active = set(payment_methods)
      keyboard: list[list[InlineKeyboardButton]] = []
      if "stars" in active:
          keyboard.append(
              [
                  InlineKeyboardButton(
                      text="⭐ Telegram Stars — 99 ★",
                      callback_data="gift_stars",
                      style="primary",
                  )
              ]
          )
      if "crypto_pay" in active:
          keyboard.append(
              [InlineKeyboardButton(text=CRYPTO_PAY_BUTTON, callback_data="gift_crypto")]
          )
      keyboard.append([_MTPROXY_BACK])
      return InlineKeyboardMarkup(inline_keyboard=keyboard)
  ```

- [ ] **Minimal production GREEN — fetch and render each new screen.** Change
  MTProxy and gift opening handlers to accept `deps: Dependencies`, call
  `await deps.payments.get_stars_invoice()` once, and pass
  `invoice.payment_methods`. VPN reuses its existing single
  `get_vpn_stars_invoice()` result for both price and methods. The three handler
  bodies keep their existing first `await callback.answer()` and use these
  exact rendering expressions immediately after it:

  ```python
  # process_boost_paid
  invoice = await deps.payments.get_stars_invoice()
  await callback.message.edit_text(
      text=(
          PAYMENT_METHODS_TEXT
          if invoice.payment_methods
          else "Оплата временно недоступна"
      ),
      reply_markup=keyboards.payment_methods(
          payment_methods=invoice.payment_methods,
      ),
  )

  # process_gift_certificate
  invoice = await deps.payments.get_stars_invoice()
  await callback.message.edit_text(
      text=(
          GIFT_CERTIFICATE_TEXT
          if invoice.payment_methods
          else "Оплата временно недоступна"
      ),
      reply_markup=keyboards.gift_certificate_payment_methods(
          payment_methods=invoice.payment_methods,
      ),
  )

  # process_vpn after its existing get_vpn_stars_invoice call
  await callback.message.edit_text(
      text=(
          VPN_MENU_TEXT
          if stars_invoice.payment_methods
          else "Оплата временно недоступна"
      ),
      reply_markup=keyboards.vpn_payment_methods(
          stars_price=stars_invoice.prices[0].amount,
          payment_methods=stars_invoice.payment_methods,
      ),
  )
  ```

  Do not catch backend errors as zero-state. Do not change `process_pay_stars`,
  `process_pay_crypto`, `process_vpn_pay_*`, `process_gift_*`,
  `process_successful_payment` or `show_crypto_invoice`.

- [ ] **Targeted GREEN and regression.** Repeat the RED command, then run:

  ```bash
  (cd bot && uv run pytest \
    tests/test_handlers.py::test_payment_method_screen_matrix -q)
  (cd bot && uv run pytest tests/test_handlers.py \
    tests/domains/payments/test_client.py -q)
  ```

  Expected first command: exactly 12 selected matrix cases and `12 passed`.
  The second command reruns the same matrix inside the complete handler/client
  regression set. Existing Stars payload, Crypto invoice, successful-payment
  and fulfilment routing tests must remain GREEN without semantic edits.

- [ ] **Refactor/documentation/diff gate.** Refactor only repeated test
  extraction for callback rows while GREEN. No new helper abstraction is
  required in production. Global zero-state/data-flow docs are PMT-006. Run
  `git diff --check`; batch diff is limited to four owned files.

**Completion criterion:** all 12 screen/state cases GREEN; both active always
Stars then Crypto; one active yields one payment callback; none yields exact
text plus Back only; each opening performs one product GET; old callbacks and
payment results are unchanged and regression-green.

#### Task Packet PMT-B5

- **scope_revision:** 2; **Plan IDs:** `PMT-005`.
- **Allowed/expected files:** exact four PMT-005 paths.
- **Forbidden adjacent work:** messages/config, backend, invoice/fulfilment,
  callback handlers listed read-only above, old-message activity checks, docs.
- **Non-goals:** changing price/labels/order, arbitrary callback generation,
  retry/error masking, per-product availability.
- **Dependencies:** reviewed PMT-B4.
- **Budget:** at most 4 files and 430 changed lines.
- **Done:** PMT-005 completion criterion and batch review without confirmed
  `blocking_in_scope`.

---

### Task 6: PMT-006 — Update current docs and run root integration gates

**Result:** all five current global documents describe the shipped revision 2
contract; targeted and complete backend/bot suites, migration drift, imports,
Compose and diff gates are green. This is root-owned integration work, not a
plan-implementer batch.

**Traceability:** BR-001–BR-006; AC-001–AC-008; assigned technical tasks:
documentation consistency and release-readiness verification.

**Dependencies:** PMT-B1–PMT-B5 reviewed with no confirmed blocking findings.

**Files and ownership:** root modifies only `docs/BUSINESS.md`,
`docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`, `docs/MODELS.md`,
`docs/apps/PAYMENTS.md`. Approved feature `business.md`/`architecture.md`, this
plan and every historical feature document are read-only.

- [ ] **Documentation RED audit.** Before editing, run:

  ```bash
  rg -n "PaymentMethod|payment_methods|Оплата временно недоступна" \
    docs/BUSINESS.md docs/ARCHITECTURE.md docs/CONTRACTS.md \
    docs/MODELS.md docs/apps/PAYMENTS.md
  ```

  Expected RED: current docs do not yet describe the model, response field and
  zero-state together.

- [ ] **Minimal documentation GREEN.** Add only these approved facts:

  ```markdown
  - Django admin управляет одной глобальной активностью `stars` и
    `crypto_pay`; переключатель действует для MTProxy, VPN и gift без рестарта.
  - Новое открытие экрана читает БД через существующий product GET. При двух
    активных способах порядок Stars -> Crypto Pay; при пустом списке бот
    показывает `Оплата временно недоступна` и только текущую кнопку «Назад».
  - Старые кнопки и действующие price/invoice/fulfilment flows не меняются.
  ```

  `docs/CONTRACTS.md` updates both existing product GET descriptions and exact
  JSON example with `"payment_methods": ["stars", "crypto_pay"]`, documenting
  the four allowed arrays and preserved `Bot-Auth-Token`/error semantics.
  `docs/MODELS.md` adds `PaymentMethod` with `code`, inherited `is_active` and
  no Product relation. `docs/ARCHITECTURE.md` and `docs/apps/PAYMENTS.md` record
  selector ordering, request-time no-cache flow, constrained admin and
  additive/non-reversing rollout.

- [ ] **Repeat documentation audit.** Re-run the `rg` command and manually
  verify all three concepts appear in the relevant current docs; confirm
  `git diff --name-only -- docs/features/cryptopay-all-products` is empty.

- [ ] **Run targeted backend and bot gates.** From repository root:

  ```bash
  make test ARGS="apps.payments.tests.test_models apps.payments.tests.test_selectors apps.payments.tests.test_payment_method_admin apps.payments.tests.test_payment_method_migration apps.payments.tests.test_views.test_get_product_view"
  cd bot && uv run pytest tests/domains/payments/test_client.py \
    tests/test_handlers.py -q
  cd ..
  ```

- [ ] **Run complete suites and static/runtime gates.** From repository root:

  ```bash
  make test
  cd bot && uv run pytest -q
  cd ..
  cd src && python manage.py makemigrations --settings=config.test_settings --check --dry-run
  cd ..
  python -m compileall -q src bot/src
  docker compose -f docker-compose.yml config --quiet
  git diff --check
  ```

  Expected: every command exits 0; migration command says `No changes
  detected`; no import/Compose error.

- [ ] **Scope/diff verification.** Run `git diff --name-only` and inspect the
  exact diff. Allowed feature surface is PMT-B1–PMT-B5 files, the five current
  global docs, and the three approved feature artifacts
  `business.md`/`architecture.md`/`plan.md`. No historical feature docs,
  notification/music/provider config, credentials, lockfile or deploy file may
  appear.

**Completion criterion:** current docs agree with implemented API/model/bot
semantics; all targeted/full/static/Compose/diff gates exit 0; all BR/AC and
non-goals have inspectable implementation/test evidence; publication has not
started.

#### Task Packet PMT-B6

- **scope_revision:** 2; **Plan IDs:** `PMT-006`; root-owned, no implementer.
- **Allowed/expected files:** five global docs listed in PMT-006; all
  implementation files are verification-only.
- **Forbidden adjacent work:** feature spec rewriting, historical docs,
  production code/test fixes without returning them to the owning implementer,
  env/deploy/credentials, commit/push/PR/merge/deploy.
- **Non-goals:** operational deploy docs, new behavior or hardening.
- **Dependencies:** all five implementation batches independently reviewed.
- **Budget:** at most 5 changed docs and 320 changed lines.
- **Done:** PMT-006 completion criterion; any failure is returned only to its
  owning implementer if classified `blocking_in_scope`.

---

### Task 7: PMT-007 — Record independent product acceptance

**Result:** `acceptance.md` records actual evidence for every BR/AC and
non-goal against the integrated reviewed tree. This task belongs exclusively to
`product-reviewer`; it changes no implementation or global docs.

**Traceability:** BR-001–BR-006; AC-001–AC-008; assigned technical task:
independent product acceptance.

**Dependencies:** PMT-006 complete with exact command outputs available.

**Files and ownership:** create only
`docs/features/admin-payment-method-toggles/acceptance.md`.

- [ ] **Acceptance RED audit.** Confirm the file does not yet claim acceptance
  and read the exact integrated diff plus outputs from PMT-006. Do not infer a
  pass from the plan or architecture alone.

- [ ] **Capture a reproducible pre-acceptance tree identity.** HEAD alone is
  only the committed base and must never be labelled as the integrated tree.
  From repository root, run this exact block before creating `acceptance.md`:

  ```bash
  PMT_ACCEPTANCE_PATH="docs/features/admin-payment-method-toggles/acceptance.md"
  PMT_REVIEW_BASE_HEAD="$(git rev-parse HEAD)"
  PMT_SNAPSHOT_DIR="$(mktemp -d)"
  trap 'rm -r -- "$PMT_SNAPSHOT_DIR"' EXIT

  pmt_capture_review_snapshot() {
    LC_ALL=C git status --short --untracked-files=all -- . \
      ":(exclude)$PMT_ACCEPTANCE_PATH" > "$PMT_SNAPSHOT_DIR/status.txt"
    git diff --binary --no-ext-diff "$PMT_REVIEW_BASE_HEAD" -- . \
      ":(exclude)$PMT_ACCEPTANCE_PATH" > "$PMT_SNAPSHOT_DIR/tracked.diff"
    LC_ALL=C git ls-files --others --exclude-standard -- . \
      ":(exclude)$PMT_ACCEPTANCE_PATH" | LC_ALL=C sort \
      > "$PMT_SNAPSHOT_DIR/untracked-files.txt"
    while IFS= read -r pmt_untracked_path; do
      test -n "$pmt_untracked_path"
      test -f "$pmt_untracked_path"
      pmt_file_sha256="$(
        shasum -a 256 "$pmt_untracked_path" | awk '{print $1}'
      )"
      printf '%s  %s\n' "$pmt_file_sha256" "$pmt_untracked_path"
    done < "$PMT_SNAPSHOT_DIR/untracked-files.txt" \
      > "$PMT_SNAPSHOT_DIR/untracked.sha256"
    {
      printf 'base-head\0%s\0status\0' "$PMT_REVIEW_BASE_HEAD"
      cat "$PMT_SNAPSHOT_DIR/status.txt"
      printf '\0tracked-diff\0'
      cat "$PMT_SNAPSHOT_DIR/tracked.diff"
      printf '\0untracked-files\0'
      cat "$PMT_SNAPSHOT_DIR/untracked.sha256"
    } | shasum -a 256 | awk '{print $1}' \
      > "$PMT_SNAPSHOT_DIR/tree.sha256"
  }

  pmt_capture_review_snapshot
  PMT_REVIEW_STATUS="$(cat "$PMT_SNAPSHOT_DIR/status.txt")"
  PMT_REVIEW_TREE_SHA256="$(cat "$PMT_SNAPSHOT_DIR/tree.sha256")"
  printf 'base_head=%s\nreview_tree_sha256=%s\n' \
    "$PMT_REVIEW_BASE_HEAD" "$PMT_REVIEW_TREE_SHA256"
  cat "$PMT_SNAPSHOT_DIR/status.txt"
  cat "$PMT_SNAPSHOT_DIR/untracked.sha256"
  ```

  The SHA-256 binds the exact committed base, exact status bytes, binary-safe
  tracked diff and content hashes of every untracked file. Only
  `acceptance.md` is excluded because it is the evidence document being
  written; the command covers every other tracked and untracked repository
  path, including feature artifacts. Preserve the printed base SHA, tree hash,
  exact status block and untracked manifest for the document.

- [ ] **Create evidence document.** Record `scope_revision: 2`,
  `PMT_REVIEW_BASE_HEAD` explicitly as **base HEAD**, never as integrated tree,
  `PMT_REVIEW_TREE_SHA256` as the reviewed working-tree identity, exact
  `PMT_REVIEW_STATUS`, final verdict, and a table with one row for each of
  AC-001–AC-008. The table must cite concrete tests or diff evidence: admin
  restrictions; `3 x 4` matrix; global cross-screen selector; sequential
  GET/renewal refresh; migration seed/order; unchanged callbacks/payment flows;
  allowlist/no per-product relation; old-button non-enforcement. Add PMT-006
  command outputs and a non-goal scope check.

- [ ] **Classify findings.** Use only:
  `blocking_in_scope`, `scope_change_request`, or `follow_up`.
  `changes_requested` is allowed only with a direct BR/AC/non-goal or
  diff-regression trace. Do not edit implementation to resolve findings.

- [ ] **Acceptance GREEN criterion.** Set status to `accepted` only when all
  eight AC rows are `passed`, all non-goals are preserved, PMT-006 gates are
  green and no confirmed `blocking_in_scope` remains. Otherwise record the
  exact non-accepted verdict and return findings to root.

- [ ] **Prove the reviewed tree did not change while writing evidence.** In the
  same shell, run:

  ```bash
  pmt_capture_review_snapshot
  PMT_POST_REVIEW_STATUS="$(cat "$PMT_SNAPSHOT_DIR/status.txt")"
  PMT_POST_REVIEW_TREE_SHA256="$(cat "$PMT_SNAPSHOT_DIR/tree.sha256")"
  test "$PMT_POST_REVIEW_STATUS" = "$PMT_REVIEW_STATUS"
  test "$PMT_POST_REVIEW_TREE_SHA256" = "$PMT_REVIEW_TREE_SHA256"
  git diff --check
  PMT_ACCEPTANCE_WHITESPACE="$(
    git diff --no-index --check /dev/null "$PMT_ACCEPTANCE_PATH" 2>&1 || true
  )"
  test -z "$PMT_ACCEPTANCE_WHITESPACE"
  git status --short --untracked-files=all -- "$PMT_ACCEPTANCE_PATH"
  ```

  Expected: both equality checks and `git diff --check` exit 0; the final
  status command shows only the newly created/modified `acceptance.md` within
  the product-reviewer's ownership. The trap removes only the exact temporary
  directory created by `mktemp -d`.

**Completion criterion:** acceptance records the actual base HEAD, exact
pre-acceptance status and deterministic reviewed-tree SHA-256; the same snapshot
hash/status reproduce after writing the excluded evidence file; AC-001–AC-008,
non-goals and test evidence are complete; no production/global-doc change
occurred.

#### Task Packet PMT-B7

- **scope_revision:** 2; **Plan IDs:** `PMT-007`; product-reviewer only.
- **Allowed/expected files:** feature `acceptance.md` only; all other files
  read-only.
- **Forbidden adjacent work:** implementation or doc fixes, requirement
  expansion, publication, merge/deploy.
- **Non-goals:** turning recommendations/hardening into current requirements.
- **Dependencies:** reviewed integrated diff and completed PMT-B6 evidence.
- **Budget:** 1 repository file and 280 changed lines; one automatically removed
  `mktemp -d` evidence directory outside repository ownership.
- **Done:** PMT-007 completion criterion and root validation of finding
  classifications.

---

### Task 8: PMT-008 — Publish only the reviewed feature tree as a Pull Request

**Result:** root alone creates scoped commit(s), pushes
`codex/admin-payment-method-toggles`, opens a PR into `main`, and proves local,
remote branch and PR head SHA equality with green checks.

**Traceability:** assigned technical task from `docs/DEVELOPMENT_WORKFLOW.md`
sections 4–5; no new BR/AC or product behavior.

**Dependencies:** PMT-007 accepted; all PMT-006 verification evidence is still
current; no write agent or reviewer is running.

**Files and ownership:** root may stage/commit only the exact allowlist below.
No implementer/product-reviewer owns publication. The PR is external state; no
new repository file is created by this task.

- [ ] **Pre-publication gate — verify branch, GitHub auth and full feature
  path scope.** From repository root run:

  ```bash
  PMT_FEATURE_BRANCH="$(git branch --show-current)"
  test "$PMT_FEATURE_BRANCH" = "codex/admin-payment-method-toggles"
  test "$PMT_FEATURE_BRANCH" != "main"
  gh auth status
  git fetch origin main

  PMT_SCOPE_DIR="$(mktemp -d)"
  trap 'rm -r -- "$PMT_SCOPE_DIR"' EXIT
  printf '%s\n' \
    src/apps/payments/models.py \
    src/apps/payments/admin.py \
    src/apps/payments/selectors.py \
    src/apps/payments/migrations/0008_payment_method.py \
    src/apps/payments/api/v1/serializers/get_product_serializer.py \
    src/apps/payments/api/v1/views/get_product_view.py \
    src/apps/payments/tests/test_models.py \
    src/apps/payments/tests/test_selectors.py \
    src/apps/payments/tests/test_payment_method_admin.py \
    src/apps/payments/tests/test_payment_method_migration.py \
    src/apps/payments/tests/test_views/test_get_product_view.py \
    bot/src/domains/payments/client.py \
    bot/src/keyboards.py \
    bot/src/handlers/payments.py \
    bot/src/handlers/vpn.py \
    bot/tests/domains/payments/test_client.py \
    bot/tests/test_handlers.py \
    docs/BUSINESS.md \
    docs/ARCHITECTURE.md \
    docs/CONTRACTS.md \
    docs/MODELS.md \
    docs/apps/PAYMENTS.md \
    docs/features/admin-payment-method-toggles/business.md \
    docs/features/admin-payment-method-toggles/architecture.md \
    docs/features/admin-payment-method-toggles/plan.md \
    docs/features/admin-payment-method-toggles/acceptance.md \
    | LC_ALL=C sort -u > "$PMT_SCOPE_DIR/allowed.txt"
  {
    git diff --name-only origin/main...HEAD
    git diff --name-only
    git diff --cached --name-only
    git ls-files --others --exclude-standard
  } | LC_ALL=C sort -u > "$PMT_SCOPE_DIR/actual.txt"
  comm -23 "$PMT_SCOPE_DIR/actual.txt" "$PMT_SCOPE_DIR/allowed.txt" \
    > "$PMT_SCOPE_DIR/unexpected.txt"
  test -s "$PMT_SCOPE_DIR/actual.txt"
  test ! -s "$PMT_SCOPE_DIR/unexpected.txt"
  ```

  Expected: exact feature branch, authenticated GitHub CLI, and no path outside
  the allowlist across already committed feature work, index, worktree or
  untracked files. Any unexpected path stops publication; root does not stage,
  overwrite or discard it.

- [ ] **Create only the scoped commit.** Stage the exact allowlist, inspect the
  cached diff and commit without amending/re-writing prior history:

  ```bash
  git add -- \
    src/apps/payments/models.py \
    src/apps/payments/admin.py \
    src/apps/payments/selectors.py \
    src/apps/payments/migrations/0008_payment_method.py \
    src/apps/payments/api/v1/serializers/get_product_serializer.py \
    src/apps/payments/api/v1/views/get_product_view.py \
    src/apps/payments/tests/test_models.py \
    src/apps/payments/tests/test_selectors.py \
    src/apps/payments/tests/test_payment_method_admin.py \
    src/apps/payments/tests/test_payment_method_migration.py \
    src/apps/payments/tests/test_views/test_get_product_view.py \
    bot/src/domains/payments/client.py \
    bot/src/keyboards.py \
    bot/src/handlers/payments.py \
    bot/src/handlers/vpn.py \
    bot/tests/domains/payments/test_client.py \
    bot/tests/test_handlers.py \
    docs/BUSINESS.md \
    docs/ARCHITECTURE.md \
    docs/CONTRACTS.md \
    docs/MODELS.md \
    docs/apps/PAYMENTS.md \
    docs/features/admin-payment-method-toggles/business.md \
    docs/features/admin-payment-method-toggles/architecture.md \
    docs/features/admin-payment-method-toggles/plan.md \
    docs/features/admin-payment-method-toggles/acceptance.md
  git diff --cached --check
  git diff --cached --stat
  git diff --cached
  git commit -m "feat: add global payment method toggles"
  test -z "$(git status --short --untracked-files=all)"
  PMT_LOCAL_HEAD="$(git rev-parse HEAD)"
  test "$(git rev-list --count origin/main..HEAD)" -gt 0
  ```

  Existing reviewed checkpoint commits remain intact; this command creates the
  final scoped commit for any still-uncommitted integration/docs/acceptance
  evidence. If the cached diff is empty or the worktree is not clean after the
  commit, root stops instead of manufacturing an empty/unrelated commit.

- [ ] **Push and create the PR to `main`.** Use the exact local head and an
  explicit scope/non-goal/checks body:

  ```bash
  PMT_FEATURE_BRANCH="$(git branch --show-current)"
  PMT_LOCAL_HEAD="$(git rev-parse HEAD)"
  git push -u origin "$PMT_FEATURE_BRANCH"
  test "$(git rev-parse "origin/$PMT_FEATURE_BRANCH")" = "$PMT_LOCAL_HEAD"
  PMT_PR_URL="$(gh pr create \
    --base main \
    --head "$PMT_FEATURE_BRANCH" \
    --title "Add global payment method toggles" \
    --body "scope_revision: 2

  Scope: global Django-admin activity for Telegram Stars and Crypto Pay on new MTProxy, VPN and gift payment screens.

  Non-goals: per-product settings, arbitrary providers, credentials, old-button runtime checks, price/invoice/fulfilment changes, merge or deploy.

  Checks: targeted backend/payment tests; targeted bot client/handler tests; full make test; full bot pytest; migration drift; compileall; production Compose config; product acceptance.")"
  PMT_PR_NUMBER="$(gh pr view "$PMT_PR_URL" --json number --jq '.number')"
  PMT_PR_HEAD="$(gh pr view "$PMT_PR_NUMBER" --json headRefOid --jq '.headRefOid')"
  test "$PMT_PR_HEAD" = "$PMT_LOCAL_HEAD"
  test "$(git rev-parse "origin/$PMT_FEATURE_BRANCH")" = "$PMT_PR_HEAD"
  gh pr checks "$PMT_PR_NUMBER" --watch
  test "$(gh pr view "$PMT_PR_NUMBER" --json headRefOid --jq '.headRefOid')" = \
    "$PMT_LOCAL_HEAD"
  printf 'pr_url=%s\npr_number=%s\npr_head=%s\n' \
    "$PMT_PR_URL" "$PMT_PR_NUMBER" "$PMT_PR_HEAD"
  ```

  Push rejection, missing auth, failed checks or SHA mismatch is a publication
  blocker; direct push to `main`, force-push and history rewriting are forbidden.

**Documentation:** the PR body is the publication record; no extra repository
document is added. `acceptance.md` remains the product evidence bound to its
pre-publication working-tree snapshot, while `PMT_PR_HEAD` becomes the exact
committed remote identity.

**Completion criterion:** feature branch is clean; full feature diff is within
the exact allowlist; PR base is `main`; URL/number are recorded; local head,
`origin/codex/admin-payment-method-toggles` and PR head are identical; checks
are green; PR remains open.

#### Task Packet PMT-B8

- **scope_revision:** 2; **Plan IDs:** `PMT-008`; root-only publication.
- **Allowed/expected files:** stage only the 26 listed feature paths; no new
  repository file. External mutations: scoped commit, feature-branch push and
  one PR into `main`.
- **Forbidden adjacent work:** implementer/product-reviewer publication,
  unrelated staging, amend/rebase/force-push, direct `main` push, PR merge,
  production deploy.
- **Non-goals:** changing product behavior or adding release/deploy work.
- **Dependencies:** accepted PMT-B7, current PMT-B6 checks, no concurrent
  write/review session, authenticated `gh`.
- **Budget:** existing feature paths only; one final scoped commit plus any
  already reviewed checkpoint commits; one push and one PR.
- **Done:** PMT-008 completion criterion with recorded URL, number, exact SHA
  and green checks.

---

### Task 9: PMT-009 — Run fresh final review against the exact remote PR head

**Result:** a new read-only `code-reviewer` reviews and comments on the exact PR
head SHA; root validates classifications, approved verdict, green checks and
unchanged remote head before reporting the still-open PR.

**Traceability:** assigned technical task from `docs/DEVELOPMENT_WORKFLOW.md`
section 5 and repository final-review rules; no new BR/AC or product behavior.

**Dependencies:** PMT-008 PR exists with green checks and recorded
`PMT_PR_NUMBER`, `PMT_PR_URL`, `PMT_PR_HEAD`; all file-writing agents have
stopped.

**Files and ownership:** final reviewer has repository read-only ownership and
may make exactly one external mutation: `gh pr review --comment`. Root only
coordinates, validates, and—if needed—returns confirmed blockers to original
file owners. Reviewer does not fix findings.

- [ ] **Freeze the exact review target and local tree.** Root runs:

  ```bash
  PMT_FEATURE_BRANCH="$(git branch --show-current)"
  PMT_PR_NUMBER="$(gh pr view --json number --jq '.number')"
  PMT_PR_URL="$(gh pr view "$PMT_PR_NUMBER" --json url --jq '.url')"
  PMT_LOCAL_HEAD="$(git rev-parse HEAD)"
  PMT_PR_HEAD="$(gh pr view "$PMT_PR_NUMBER" --json headRefOid --jq '.headRefOid')"
  test "$PMT_FEATURE_BRANCH" = "codex/admin-payment-method-toggles"
  test "$PMT_LOCAL_HEAD" = "$PMT_PR_HEAD"
  test "$(git rev-parse "origin/$PMT_FEATURE_BRANCH")" = "$PMT_PR_HEAD"
  test -z "$(git status --short --untracked-files=all)"
  ```

- [ ] **Launch a fresh final reviewer with an exact packet.** Root provides:
  `scope_revision: 2`, PR number/URL, exact `PMT_PR_HEAD`, BR-001–BR-006,
  AC-001–AC-008, non-goals, PMT-001–PMT-009, allowed read commands, and the
  rule that only a structured review comment is mutable. Reviewer must run
  `gh pr view`, `gh pr diff` and `gh pr checks` for that PR/head, inspect the
  complete diff and publish one `gh pr review --comment` whose body contains:

  - exact `scope_revision: 2` and a `PR_HEAD_SHA:` field whose value is the
    supplied `PMT_PR_HEAD`;
  - findings classified only as `blocking_in_scope`, `scope_change_request` or
    `follow_up`, each with its required trace; every actual blocking finding is
    a separate line beginning exactly `- blocking_in_scope: `;
  - a final verdict whose line is the **last non-empty line** of the entire
    comment: exactly `VERDICT: changes_requested` when at least one
    `blocking_in_scope` finding exists, otherwise exactly
    `VERDICT: approved`. No text, signature or footer follows that line.

  Reviewer must not edit files, commit, push, merge, close or edit the PR. Root
  compares worktree status before/after and rejects a review that changed it.

- [ ] **Validate the published review against the frozen head.** After the
  reviewer stops, root runs:

  ```bash
  test -z "$(git status --porcelain=v1 --untracked-files=all)"
  PMT_PR_NUMBER="$(gh pr view --json number --jq '.number')"
  PMT_PR_HEAD="$(gh pr view "$PMT_PR_NUMBER" --json headRefOid --jq '.headRefOid')"
  test "$(git rev-parse HEAD)" = "$PMT_PR_HEAD"
  PMT_REPO="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"
  PMT_FINAL_REVIEW_BODY="$(gh api \
    "repos/$PMT_REPO/pulls/$PMT_PR_NUMBER/reviews" \
    --jq "[.[] | select(.commit_id == \"$PMT_PR_HEAD\")][-1].body")"
  printf '%s\n' "$PMT_FINAL_REVIEW_BODY" | \
    rg -Fq "scope_revision: 2"
  printf '%s\n' "$PMT_FINAL_REVIEW_BODY" | \
    rg -Fq "PR_HEAD_SHA: $PMT_PR_HEAD"
  PMT_FINAL_REVIEW_LAST_LINE="$(
    printf '%s\n' "$PMT_FINAL_REVIEW_BODY" | \
      awk 'NF {pmt_last_nonempty=$0} END {print pmt_last_nonempty}'
  )"
  case "$PMT_FINAL_REVIEW_LAST_LINE" in
    "VERDICT: approved")
      if printf '%s\n' "$PMT_FINAL_REVIEW_BODY" | \
        rg -q '^- blocking_in_scope: .+'; then
        exit 1
      fi
      ;;
    "VERDICT: changes_requested")
      if ! printf '%s\n' "$PMT_FINAL_REVIEW_BODY" | \
        rg -q '^- blocking_in_scope: .+'; then
        exit 1
      fi
      ;;
    *)
      exit 1
      ;;
  esac
  ```

  The first and second status gates are both exact empty porcelain output, so
  equality is established without relying on a shell variable surviving the
  reviewer process boundary.

  Root manually validates every classification before issuing fixes. Only
  confirmed `blocking_in_scope` items may become a fix batch; scope-change
  requests and follow-ups are reported but not assigned as current work.

- [ ] **Execute the exact-head fix loop when required.** For confirmed
  blockers, root returns only those items to the original owning implementer,
  runs a new independent batch review and PMT-006 relevant/full gates, then
  reruns PMT-007 product acceptance so `acceptance.md` binds the repaired tree.
  Only after re-acceptance does root create a new scoped commit and push
  normally. Root then refreshes and proves the new identity:

  ```bash
  PMT_FEATURE_BRANCH="$(git branch --show-current)"
  PMT_PR_NUMBER="$(gh pr view --json number --jq '.number')"
  PMT_PR_HEAD="$(gh pr view "$PMT_PR_NUMBER" --json headRefOid --jq '.headRefOid')"
  test "$PMT_PR_HEAD" = "$(git rev-parse HEAD)"
  test "$PMT_PR_HEAD" = "$(git rev-parse "origin/$PMT_FEATURE_BRANCH")"
  gh pr checks "$PMT_PR_NUMBER" --watch
  ```

  Every push invalidates the old review. Root launches another fresh final
  reviewer against the new exact SHA and repeats validation; no stale approval
  can complete this task.

- [ ] **Final immutable-head gate.** When the exact-head review says approved,
  root runs:

  ```bash
  PMT_FEATURE_BRANCH="$(git branch --show-current)"
  PMT_PR_NUMBER="$(gh pr view --json number --jq '.number')"
  PMT_REPO="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"
  PMT_PR_HEAD="$(gh pr view "$PMT_PR_NUMBER" --json headRefOid --jq '.headRefOid')"
  test "$PMT_PR_HEAD" = "$(git rev-parse HEAD)"
  test "$PMT_PR_HEAD" = "$(git rev-parse "origin/$PMT_FEATURE_BRANCH")"
  gh pr checks "$PMT_PR_NUMBER" --watch
  test "$(gh pr view "$PMT_PR_NUMBER" --json headRefOid --jq '.headRefOid')" = \
    "$PMT_PR_HEAD"
  test "$(gh pr view "$PMT_PR_NUMBER" --json state --jq '.state')" = "OPEN"
  test "$(gh pr view "$PMT_PR_NUMBER" --json baseRefName --jq '.baseRefName')" = \
    "main"
  PMT_FINAL_REVIEW_BODY="$(gh api \
    "repos/$PMT_REPO/pulls/$PMT_PR_NUMBER/reviews" \
    --jq "[.[] | select(.commit_id == \"$PMT_PR_HEAD\")][-1].body")"
  printf '%s\n' "$PMT_FINAL_REVIEW_BODY" | \
    rg -Fq "PR_HEAD_SHA: $PMT_PR_HEAD"
  PMT_FINAL_REVIEW_LAST_LINE="$(
    printf '%s\n' "$PMT_FINAL_REVIEW_BODY" | \
      awk 'NF {pmt_last_nonempty=$0} END {print pmt_last_nonempty}'
  )"
  test "$PMT_FINAL_REVIEW_LAST_LINE" = "VERDICT: approved"
  if printf '%s\n' "$PMT_FINAL_REVIEW_BODY" | \
    rg -q '^- blocking_in_scope: .+'; then
    exit 1
  fi
  ```

  Root reports `PMT_PR_URL`, `PMT_PR_HEAD`, checks and final verdict to the
  user, leaving the PR open. This report is not merge or deploy authorization.

**Documentation:** final structured PR review comment and root report are the
workflow evidence; no repository doc changes are made after exact-head review.

**Completion criterion:** latest review comment is from a fresh reviewer of the
current PR head, names that exact SHA and ends approved; classifications are
root-validated; checks are green; local/remote/PR SHA equality holds after
checks; PR is open against `main`; merge/deploy did not occur.

#### Task Packet PMT-B9

- **scope_revision:** 2; **Plan IDs:** `PMT-009`; root coordination plus fresh
  read-only final reviewer.
- **Allowed/expected files:** repository entirely read-only during final
  review. Only external reviewer mutation is one structured PR review comment;
  confirmed fix batches return to their original file owners.
- **Forbidden adjacent work:** reviewer fixes, unclassified mandatory changes,
  concurrent write agents, stale-SHA approval, push/merge/close/edit by
  reviewer, direct `main` push, merge or deploy by root.
- **Non-goals:** product expansion, optional hardening, merge/deploy.
- **Dependencies:** PMT-B8 exact remote head and checks; fresh reviewer per SHA.
- **Budget:** one final reviewer/comment per exact SHA; fix loops only for
  root-confirmed `blocking_in_scope` and only within original ownership.
- **Done:** PMT-009 completion criterion; user receives open PR URL, verified
  head SHA, green checks and approved exact-head verdict.

---

## Traceability Matrix

| Requirement | Direct implementation and evidence |
|---|---|
| BR-001 / AC-001 / AC-003 | PMT-001 global model+selector; PMT-002 constrained admin; PMT-003 same list on both APIs; PMT-005 all screens |
| BR-002 / AC-001 | PMT-001 exact choices/allowlist; PMT-002 no add/delete/code editing |
| BR-003 / AC-004 | PMT-003 sequential GET with no cache; PMT-005 one product GET on each opening including `boost_paid` |
| BR-004 / AC-002 | PMT-005 full `3 x 4` matrix, exact zero-state and Back-only keyboard |
| BR-005 / AC-007 | PMT-001 one global code row and ordered allowlist; absence of Product relation/per-product fields/framework |
| BR-006 / AC-005 | PMT-001 idempotent active seed and order test; PMT-003/004/005 initial both-active regressions |
| AC-006 | PMT-003 preserved fields/errors/auth; PMT-005 unchanged callback/invoice/successful-payment regressions |
| AC-008 | PMT-005 opening-only filtering and explicit read-only old callback bodies |
| Docs/integration | PMT-006 current global docs, full suites, migration/import/Compose/diff gates |
| Product acceptance | PMT-007 deterministic base+status+tracked/untracked snapshot and independent evidence for every BR/AC/non-goal |
| Publication | PMT-008 scoped commit, feature push, PR URL/number, exact local/remote/PR SHA equality and checks |
| Final PR review | PMT-009 fresh reviewer per exact PR head, classified comment, fix loop, immutable-head checks and open-PR handoff |

## Plan Self-Review

- **Spec coverage:** BR-001–BR-006 and AC-001–AC-008 each have direct rows in
  the traceability matrix and executable RED/GREEN evidence; no approved
  requirement is unassigned.
- **Placeholder scan:** no deferred-work markers, unspecified error handling or
  unnamed test step remain. Every code block is executable content; ellipsis
  tokens occur only in standard PEP typing `tuple[str, ...]` and Git's exact
  three-dot comparison `origin/main...HEAD`.
- **Type consistency:** DB/API/bot mapping is fixed as
  `tuple[str, ...]` -> JSON `list[str]` -> `tuple[str, ...]`; all three keyboard
  builders consume the same exact tuple; codes are exactly `stars` and
  `crypto_pay`.
- **Workflow coverage:** PMT-007 binds acceptance to the actual uncommitted
  integrated tree instead of mislabelling HEAD; PMT-008 and PMT-009 cover the
  required root publication and exact-head final review gates. Merge/deploy
  remain explicitly prohibited. The plan has nine atomic items, within the
  ten-item limit. PMT-005 executes the exact 12-case matrix node in RED and
  targeted GREEN; PMT-009 treats only the exact last non-empty review line as
  the verdict and validates both allowed verdict branches.
- **Scope classification:** the two confirmed `blocking_in_scope` plan-review
  findings are resolved by PMT-007–PMT-009. No remaining
  `blocking_in_scope`, `scope_change_request` or `follow_up` was identified,
  and no product behavior/component/contract beyond approved revision 2 was
  added.

Root integration/publishing remains outside implementer tasks. After architect
review and root approval, execution begins with PMT-B1; commit/push/PR and final
review coordination are owned only by root in PMT-B8/PMT-B9. Completion leaves
the PR open; merge and deploy require later separate explicit user gates.
