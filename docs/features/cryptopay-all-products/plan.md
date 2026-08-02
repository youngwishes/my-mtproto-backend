# Crypto Pay for All Products Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

- **Status:** approved
- **Scope revision:** 2 (immutable; revision 1 is superseded)
- **Architecture review:** approved; no blocking findings, scope change
  requests or follow-ups.
- **Route:** обычная продуктовая фича; реализация начинается только после
  утверждения плана главным оркестратором.

**Goal:** Добавить Crypto Pay вторым способом оплаты для текущих 30-дневных
MTProto, VPN и gift-продуктов с точной RUB-суммой, повторным использованием
30-минутного счёта, exact-once выдачей, post-commit результатом в Telegram и
10-минутным recovery через reconciliation, не меняя Telegram Stars.

**Architecture:** Django владеет локальным `CryptoPaymentIntent`, вызовами
Crypto Pay, HMAC+secret-path webhook и условным exact-once claim, после которого
переиспользует существующие MTProto/VPN/gift fulfillment-сервисы. Celery
доставляет durable user result и каждые 10 минут сверяет незавершённые intent;
aiogram-бот только создаёт счёт через `Bot-Auth-Token` API и показывает URL.

**Tech Stack:** Python 3.13, Django 6, Django REST Framework, SQLite, Celery
5.6/Redis, `requests` + `responses`, aiogram 3, `httpx` + `respx`,
`unittest`/pytest, Docker Compose, Ansible, Markdown.

## Global Constraints

- Единственные источники обязательного поведения — approved
  `docs/features/cryptopay-all-products/business.md` и approved архитектурное
  решение `architecture.md`, оба `scope_revision: 2`: BR-001..BR-012,
  AC-001..AC-012 и их non-goals.
- Новое пользовательское поведение, обязательный edge case, компонент,
  контракт или расширение non-goals требует `scope_change_request`; reviewer не
  превращает hardening/follow-up в обязательную правку.
- Реализация каждого пункта идёт через TDD: один конкретный RED, проверка
  ожидаемой причины, минимальный GREEN, затем refactor только на зелёных тестах.
- Backend services — `@final` dataclass с `kw_only=True, slots=True,
  frozen=True`, keyword-only `__call__`; сервисные зависимости инъецируются,
  wiring находится в module-level factory.
- ORM остаётся в `src/apps/payments/selectors.py`; DTO — в
  `services/dtos/`, exceptions — в `exceptions.py`, enum — в `enums.py`;
  public symbols явно экспортируются из каждого затронутого package
  `__init__.py`.
- `CryptoPaymentIntent` наследует `BaseDjangoModel`; `created_at`, `updated_at`
  и `is_active` не дублируются. SQLite `select_for_update()` не используется как
  единственная защита: арбитры — partial constraints и conditional `UPDATE`.
- `Product.price` уже хранит копейки в `DecimalField`: только
  `Decimal(product.price) / Decimal("100")`, quantize до двух знаков, без float,
  отдельной crypto-price или курса. Gift использует активный `mtproto_30d`.
- `createInvoice` содержит только opaque UUID payload и публичное название;
  Telegram ID, username, email и иная PII провайдеру не передаются. Активы
  строго `USDT,TON`, expiry строго `1800` секунд.
- Crypto Pay token и webhook secret существуют только в backend Django/Celery;
  bot settings/env их не получают. Секреты, signature, raw body, PII, invoice
  URL, gift code и VPN URL запрещены в log/admin warning.
- Stars buttons/callbacks, XTR invoice payloads, successful-payment routing и
  legacy non-XTR fulfillment сохраняют текущую семантику и regression tests.
- Не добавлять новый dependency, Django app, provider framework, price/rate,
  recurring payment, refund, wallet, manual mark-paid, audit/event/outbox model,
  monitoring infrastructure или изменение продукта/duration.
- Не читать, не менять и не включать в audit `apps/music/`.
- Один `plan-implementer` получает один batch не более чем из двух task IDs.
  Здесь каждый batch содержит ровно один ID. Implementer не создаёт branch,
  commit, push или PR; root может сделать commit checkpoint только после
  отдельного read-only batch review.
- Merge и production deploy не входят в план. PR остаётся открытым; merge и
  последующий production deploy требуют отдельных явных разрешений пользователя.

---

## Complete File Map and Responsibilities

### Payment persistence and provider boundary

- `src/apps/payments/enums.py` — `CRYPTO_PAY` provider и intent lifecycle enum.
- `src/apps/payments/models.py` — `CryptoPaymentIntent` и Crypto-only partial
  uniqueness для `Payment`.
- `src/apps/payments/selectors.py` — все intent reads, reservations,
  conditional transitions, payment/result lookups и reconciliation querysets.
- `src/apps/payments/admin.py` — read-only diagnostic intent admin.
- `src/apps/payments/migrations/0007_crypto_payment_intent.py` — additive schema,
  indexes/constraints/provider choice без переписывания legacy rows.
- `src/apps/payments/clients/crypto_pay.py` и `clients/__init__.py` — тонкий
  `requests` adapter для `createInvoice`/`getInvoices`.
- `src/apps/payments/exceptions.py` — create/provider/webhook/retryable domain
  errors с безопасными сообщениями.
- `src/apps/payments/services/dtos/crypto_pay_dtos.py` и `dtos/__init__.py` —
  decimal/time-safe provider, API, validation, apply и warning DTO.

### Payment orchestration, API and asynchronous delivery

- `src/apps/payments/services/create_crypto_invoice.py` — create/reuse/lease
  state machine; provider HTTP вне долгой SQLite transaction.
- `src/apps/payments/services/apply_crypto_payment.py` — conditional exact-once
  claim и существующие MTProto/VPN/gift services внутри одной atomic boundary.
- `src/apps/payments/services/validate_crypto_invoice.py` — единая semantic
  validation для webhook и reconciliation.
- `src/apps/payments/services/reconcile_crypto_payments.py` — bounded provider
  batches, per-invoice isolation и counters.
- `src/apps/payments/services/create_payment_service.py` — только DI-safe issue
  service и backward-compatible `send_success_notification=True` switch.
- `src/apps/payments/services/__init__.py` — явные exports новых services/factories.
- `src/apps/payments/tasks.py` — user-result delivery, safe admin warning и
  reconciliation Celery entrypoints/retries.
- `src/apps/payments/api/v1/serializers/crypto_pay_serializers.py` — strict
  create response/request и signed webhook parsing после HMAC.
- `src/apps/payments/api/v1/views/crypto_pay_views.py` — BotAuth create endpoint,
  raw-body HMAC webhook и утверждённая HTTP semantics.
- serializer/view `__init__.py` и `api/v1/urls.py` — public exports/routes.
- `src/apps/notifications/migrations/0011_seed_crypto_purchase_templates.py` —
  только отсутствующие result templates для VPN и gift; Stars templates не
  меняются.

### Configuration, logging and bot

- `src/config/settings/payments.py` — backend-only token/base URL/secret/timeout.
- `src/config/settings/celery.py` — exact `*/10` reconciliation schedule.
- `src/config/middlewares.py` — webhook path redaction и полный запрет body/header
  logging для webhook route.
- `.env.example` — backend Crypto Pay variables без значений; bot env не меняется.
- `bot/src/domains/payments/client.py` и `__init__.py` — exact-string
  `CryptoInvoice` DTO и `create_crypto_invoice` BotAuth call.
- `bot/src/keyboards.py`, `messages.py`, `handlers/payments.py`,
  `handlers/vpn.py` — Stars first, Crypto second, три callbacks и URL response.

### Tests and documents

- New backend tests use `unittest`, `TransactionTestCase`, `responses` and
  `apps.core.bot.TelegramBot`/core transport patch patterns already used by repo.
- Bot tests extend `bot/tests/domains/payments/test_client.py` and
  `bot/tests/test_handlers.py` with `respx` and lightweight fakes.
- `docs/BUSINESS.md`, `ARCHITECTURE.md`, `CONTRACTS.md`, `MODELS.md`,
  `docs/apps/PAYMENTS.md`, `docs/DEPLOY.md` document only the approved flow,
  contracts, lifecycle, rollout/rollback and testnet readiness.
- `docs/features/cryptopay-all-products/acceptance.md` — final acceptance
  evidence. It is created/updated exclusively by `product-reviewer` after
  CPAY-001..CPAY-009 integration; no plan implementer owns or edits it.

## Interfaces Shared Across Tasks

The following exact names and types are fixed by this plan and must not drift
between task packets:

```python
class CryptoPaymentIntentStatusEnum(enum.StrEnum):
    CREATING = "creating"
    ACTIVE = "active"
    LOCAL_EXPIRED = "local_expired"
    PROCESSING = "processing"
    RETRYABLE = "retryable"
    FULFILLED = "fulfilled"
    CREATE_FAILED = "create_failed"
    PROVIDER_EXPIRED = "provider_expired"

@dataclass(kw_only=True, slots=True, frozen=True)
class CryptoInvoiceDTO(BaseServiceDTO):
    invoice_id: int
    status: str
    currency_type: str
    fiat: str | None
    amount: Decimal
    accepted_assets: frozenset[str]
    paid_asset: str | None
    payload: str
    bot_invoice_url: str
    created_at: datetime
    expiration_date: datetime
    paid_at: datetime | None

@dataclass(kw_only=True, slots=True, frozen=True)
class CreateCryptoInvoiceIn(BaseServiceDTO):
    username: str
    purchase_kind: str

@dataclass(kw_only=True, slots=True, frozen=True)
class CreateCryptoInvoiceOut(BaseServiceDTO):
    invoice_url: str
    rub_amount: Decimal
    expires_at: datetime
    reused: bool

@dataclass(kw_only=True, slots=True, frozen=True)
class ValidatedCryptoPaymentDTO(BaseServiceDTO):
    intent_id: int
    invoice: CryptoInvoiceDTO

@dataclass(kw_only=True, slots=True, frozen=True)
class CryptoWebhookWarningDTO(BaseServiceDTO):
    reason: str
    update_id: int | None
    invoice_id: int | None
    intent_id: int | None

@dataclass(kw_only=True, slots=True, frozen=True)
class ApplyCryptoPaymentOut(BaseServiceDTO):
    fulfilled: bool
    already_fulfilled: bool

CryptoPayClient.create_invoice(
    *, amount: Decimal, payload: str, description: str
) -> CryptoInvoiceDTO
CryptoPayClient.get_invoices(*, invoice_ids: list[int]) -> list[CryptoInvoiceDTO]

CreateOrReuseCryptoInvoiceService.__call__(
    *, request: CreateCryptoInvoiceIn
) -> CreateCryptoInvoiceOut
ValidateCryptoInvoiceService.__call__(
    *, update_id: int | None, invoice: CryptoInvoiceDTO
) -> ValidatedCryptoPaymentDTO | CryptoWebhookWarningDTO
ApplyCryptoPaymentService.__call__(
    *, payment: ValidatedCryptoPaymentDTO
) -> ApplyCryptoPaymentOut

notify_crypto_purchase_task(intent_id: int) -> None
warn_crypto_webhook_admin_task(
    warning: dict[str, int | str | None]
) -> None
reconcile_crypto_payments_task() -> dict[str, int]
```

The concrete injected dependency shapes and module-level factory wiring are:

```python
class EnqueueCryptoNotification(Protocol):
    def __call__(self, *, intent_id: int) -> None:
        """Enqueue durable result delivery after transaction commit."""

class NotifyPaymentSuccess(Protocol):
    def __call__(self, *, chat_id: int, expired_date: str) -> None:
        """Send the existing direct MTProto success notification."""

@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CreateOrReuseCryptoInvoiceService:
    crypto_pay_client: CryptoPayClient
    clock: Callable[[], datetime]

@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ApplyCryptoPaymentService:
    create_payment_service: CreatePaymentService
    fulfill_vpn_purchase_service: FulfillVPNPurchaseService
    create_gift_certificate_service: CreateGiftCertificateService
    enqueue_notification: EnqueueCryptoNotification
    clock: Callable[[], datetime]

@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ValidateCryptoInvoiceService:
    """Pure semantic validator; ORM reads use payments selectors."""

@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReconcileCryptoPaymentsService:
    crypto_pay_client: CryptoPayClient
    validate_invoice_service: ValidateCryptoInvoiceService
    apply_payment_service: ApplyCryptoPaymentService
    enqueue_notification: EnqueueCryptoNotification

def _enqueue_crypto_notification(*, intent_id: int) -> None:
    from apps.payments.tasks import notify_crypto_purchase_task
    notify_crypto_purchase_task.delay(intent_id)

def get_create_or_reuse_crypto_invoice_service() -> CreateOrReuseCryptoInvoiceService:
    return CreateOrReuseCryptoInvoiceService(
        crypto_pay_client=get_crypto_pay_client(),
        clock=timezone.now,
    )

def get_validate_crypto_invoice_service() -> ValidateCryptoInvoiceService:
    return ValidateCryptoInvoiceService()

def get_apply_crypto_payment_service() -> ApplyCryptoPaymentService:
    return ApplyCryptoPaymentService(
        create_payment_service=get_create_payment_service(),
        fulfill_vpn_purchase_service=get_fulfill_vpn_purchase_service(),
        create_gift_certificate_service=get_create_gift_certificate_service(),
        enqueue_notification=_enqueue_crypto_notification,
        clock=timezone.now,
    )

def get_reconcile_crypto_payments_service() -> ReconcileCryptoPaymentsService:
    return ReconcileCryptoPaymentsService(
        crypto_pay_client=get_crypto_pay_client(),
        validate_invoice_service=get_validate_crypto_invoice_service(),
        apply_payment_service=get_apply_crypto_payment_service(),
        enqueue_notification=_enqueue_crypto_notification,
    )
```

Exception inheritance and construction are fixed as follows; client exceptions
never contain token, raw response or request body:

```python
class CryptoPayClientError(RuntimeError):
    """Safe internal provider failure used by service mapping/Celery retry."""

class CryptoInvoiceCreationInProgress(BaseServiceError):
    """Счёт уже создаётся. Повторите попытку через несколько секунд."""

class CryptoInvoiceUnavailable(BaseInfraError):
    """Не удалось создать счёт Crypto Pay. Попробуйте ещё раз."""

class CryptoPaymentRetryable(BaseInfraError):
    """Оплата подтверждена, выдача будет повторена автоматически."""

raise CryptoInvoiceCreationInProgress(request.username, reason_code="creating")
raise CryptoInvoiceUnavailable(request.username, reason_code="provider_unavailable")
```

Any additional `BaseServiceError`/`BaseInfraError` in these tasks follows the
same constructor rule: `telegram_id` is the first positional argument; safe
reason codes are keyword context. `CryptoPayClientError` deliberately remains a
plain internal `RuntimeError` because reconciliation has no user Telegram ID.

Provider field `expiration_date` maps to local `provider_expires_at`; API field
remains `expires_at`. `accepted_assets` is normalized once to a `frozenset` and
compared with `frozenset({"USDT", "TON"})`; serialization back to provider uses
the exact string `"USDT,TON"`.

## Dependency and Batch Graph

```text
CPAY-B1 CPAY-001
    |
CPAY-B2 CPAY-002
    |
CPAY-B3 CPAY-003
   / \
  v   v
CPAY-B4 CPAY-004        CPAY-B7 CPAY-007   (parallel: src/ vs bot/)
    |                       |
CPAY-B5 CPAY-005        CPAY-B8 CPAY-008   (parallel: src/ vs bot/)
    |
CPAY-B6 CPAY-006
   \_______________________/
               |
        CPAY-B9 CPAY-009
```

- `CPAY-B4` and `CPAY-B7` are the first allowed parallel pair: all dependencies
  are green/reviewed and their files do not overlap.
- `CPAY-B5` and `CPAY-B8` are the second allowed parallel pair for the same
  reason. `CPAY-B6` may start after approved `CPAY-B5`; it never runs in
  parallel with another writer of `src/apps/payments/tasks.py`.
- All other batches are sequential. Root waits for every writer before starting
  each read-only reviewer and checks `git status --short` before/after review.
- Each `Task packet CPAY-B*` consists of its task section as a whole: the
  section's **Traceability** is the assigned BR/AC, **Dependencies** are the
  packet dependencies, **Files and ownership** are the allowed/expected files,
  and its packet paragraph adds forbidden adjacent work, inherited Global
  Constraints non-goals, budget and completion/review gate. Packets must be
  handed off without omitting those preceding fields.

---

### CPAY-001 — Persist intent lifecycle, constraints, selectors and read-only admin

**Result:** additive persistence stores one initiator-owned Crypto purchase,
arbitrates active create races and exact-once Payment identity on SQLite, exposes
all later conditional operations through selectors, and provides diagnostics
without a mark-paid path.

**Traceability:** BR-004..BR-007, BR-009..BR-010; AC-004..AC-010. Technical
assignment: architecture sections 2, 5, 8 and 9.

**Dependencies:** approved revision 2 artifacts only.

**Files and ownership:**

- Modify: `src/apps/payments/enums.py`, `models.py`, `selectors.py`, `admin.py`,
  `tests/factories.py`.
- Create: `src/apps/payments/migrations/0007_crypto_payment_intent.py`.
- Create/Test: `src/apps/payments/tests/test_crypto_models.py`,
  `test_crypto_selectors.py`, `test_crypto_migrations.py`,
  `test_crypto_admin.py`.
- Ownership is limited to provider/intent schema, lifecycle selectors and
  diagnostic admin. No HTTP client, service, API, task, bot or global docs.

**Interfaces consumed/produced:** consumes `SystemUser`, `Product`, `Payment`,
`PaymentKindEnum`, `ProductCodeEnum`, `BaseDjangoModel`. Produces
`PaymentProviderEnum.CRYPTO_PAY`, `CryptoPaymentIntentStatusEnum`,
`CryptoPaymentIntent` and selectors with these exact signatures:

```python
get_reusable_crypto_intent(
    *, initiator_id: int, purchase_kind: str, now: datetime
) -> CryptoPaymentIntent | None
get_creating_crypto_intent(
    *, initiator_id: int, purchase_kind: str
) -> CryptoPaymentIntent | None
create_crypto_intent(
    *, initiator_id: int, purchase_kind: str, product_code: str,
    rub_amount: Decimal, public_id: UUID
) -> CryptoPaymentIntent
get_crypto_intent_by_provider_invoice_id(
    *, provider_invoice_id: int
) -> CryptoPaymentIntent | None
get_crypto_intent_by_id(*, intent_id: int) -> CryptoPaymentIntent | None
get_crypto_intent_for_notification(
    *, intent_id: int
) -> CryptoPaymentIntent | None
get_unfinished_crypto_intents(*, limit: int) -> QuerySet[CryptoPaymentIntent]
get_unnotified_fulfilled_crypto_intents(
    *, limit: int
) -> QuerySet[CryptoPaymentIntent]
get_payment_by_identity(
    *, provider: str, charge_id: str, kind: str
) -> Payment | None
create_subscription_payment(
    *, user_id: int, key_id: int, charge_id: str, provider: str
) -> Payment
conditionally_transition_crypto_intent(
    *, intent_id: int, from_statuses: tuple[str, ...], to_status: str,
    updates: dict[str, object]
) -> int
claim_crypto_intent_for_fulfillment(
    *, intent_id: int, attempted_at: datetime
) -> int
finalize_crypto_intent_fulfillment(
    *, intent_id: int, payment_id: int, paid_at: datetime,
    fulfilled_at: datetime
) -> int
mark_crypto_intent_retryable(*, intent_id: int, error_code: str) -> int
mark_crypto_notification_sent(*, intent_id: int, sent_at: datetime) -> int
mark_crypto_intent_provider_expired(*, intent_id: int) -> int
expire_active_crypto_intent(
    *, initiator_id: int, purchase_kind: str, now: datetime
) -> int
fail_stale_creating_crypto_intent(
    *, initiator_id: int, purchase_kind: str, stale_before: datetime
) -> int
reserve_crypto_intent_or_read_winner(
    *, initiator_id: int, purchase_kind: str, product_code: str,
    rub_amount: Decimal, public_id: UUID
) -> tuple[CryptoPaymentIntent, bool]
fail_crypto_intent_creation(*, intent_id: int, error_code: str) -> int
activate_crypto_intent_from_provider(
    *, intent_id: int, invoice: CryptoInvoiceDTO
) -> CryptoPaymentIntent
```

- [ ] **RED model/migration tests.** Add exact tests
  `TestCryptoPaymentIntentModel.test_only_one_creating_or_active_intent_per_initiator_and_kind`,
  `test_provider_invoice_id_is_unique_when_present`,
  `TestPaymentModel.test_crypto_payment_identity_is_unique_for_all_three_kinds`,
  `test_legacy_subscription_duplicates_remain_allowed`,
  `TestCryptoPaymentMigration.test_forward_preserves_legacy_products_payments_and_gifts`,
  and `test_schema_contains_crypto_only_partial_constraints`.

  ```python
  class TestCryptoPaymentIntentModel(TestCase):
      def test_only_one_creating_or_active_intent_per_initiator_and_kind(self) -> None:
          user = SystemUserFactory()
          CryptoPaymentIntentFactory(
              initiator=user,
              purchase_kind=PaymentKindEnum.SUBSCRIPTION,
              status=CryptoPaymentIntentStatusEnum.ACTIVE,
          )
          with self.assertRaises(IntegrityError), transaction.atomic():
              CryptoPaymentIntentFactory(
                  initiator=user,
                  purchase_kind=PaymentKindEnum.SUBSCRIPTION,
                  status=CryptoPaymentIntentStatusEnum.CREATING,
              )

      def test_crypto_payment_identity_is_unique_for_all_three_kinds(self) -> None:
          for kind in PaymentKindEnum:
              with self.subTest(kind=kind):
                  PaymentFactory(
                      provider=PaymentProviderEnum.CRYPTO_PAY,
                      charge_id=f"invoice-{kind}",
                      kind=kind,
                  )
                  with self.assertRaises(IntegrityError), transaction.atomic():
                      PaymentFactory(
                          provider=PaymentProviderEnum.CRYPTO_PAY,
                          charge_id=f"invoice-{kind}",
                          kind=kind,
                      )
  ```

  Complete lifecycle constraint cases:

  | Existing | New | Same user/kind allowed? |
  |---|---|---|
  | `CREATING` | `ACTIVE` | no |
  | `ACTIVE` | `CREATING` | no |
  | `LOCAL_EXPIRED` | `CREATING` | yes |
  | `CREATE_FAILED` | `CREATING` | yes |
  | `FULFILLED` | `ACTIVE` | yes |

- [ ] **Run RED.** From root:

  ```bash
  make test ARGS="apps.payments.tests.test_crypto_models apps.payments.tests.test_crypto_migrations"
  ```

  Expected: import/model lookup failures for `CryptoPaymentIntent`,
  `CRYPTO_PAY` and migration `0007`; no pre-existing test failure is acceptable.

- [ ] **Minimal schema GREEN.** Add UUID `public_id`, initiator FK,
  `purchase_kind`, `product_code`, `rub_amount` (`max_digits=10`,
  `decimal_places=2`), lifecycle `status`, nullable unique provider ID/URL/time
  fields, paid/attempted/fulfilled/notified timestamps, protected nullable
  one-to-one `payment` and `last_error_code` (`max_length=64`, blank). Add
  partial unique `(initiator, purchase_kind)` only for `CREATING|ACTIVE` and
  partial unique `(provider, charge_id, kind)` only for
  `provider="crypto_pay"`; generate additive migration 0007 without data rewrite.

  ```python
  class CryptoPaymentIntent(BaseDjangoModel):
      public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
      initiator = models.ForeignKey(
          "users.SystemUser", on_delete=models.PROTECT,
          related_name="crypto_payment_intents",
      )
      purchase_kind = models.CharField(max_length=32, choices=PaymentKindEnum.choices())
      product_code = models.CharField(max_length=32)
      rub_amount = models.DecimalField(max_digits=10, decimal_places=2)
      status = models.CharField(
          max_length=32,
          choices=CryptoPaymentIntentStatusEnum.choices(),
          default=CryptoPaymentIntentStatusEnum.CREATING,
      )
      provider_invoice_id = models.PositiveBigIntegerField(null=True, blank=True, unique=True)
      provider_invoice_url = models.URLField(max_length=512, blank=True)
      provider_created_at = models.DateTimeField(null=True, blank=True)
      provider_expires_at = models.DateTimeField(null=True, blank=True)
      paid_at = models.DateTimeField(null=True, blank=True)
      fulfillment_attempted_at = models.DateTimeField(null=True, blank=True)
      fulfilled_at = models.DateTimeField(null=True, blank=True)
      notification_sent_at = models.DateTimeField(null=True, blank=True)
      payment = models.OneToOneField(
          "payments.Payment", on_delete=models.PROTECT,
          null=True, blank=True, related_name="crypto_intent",
      )
      last_error_code = models.CharField(max_length=64, blank=True)

      class Meta:
          constraints = [
              models.UniqueConstraint(
                  fields=("initiator", "purchase_kind"),
                  condition=models.Q(status__in=("creating", "active")),
                  name="uniq_active_crypto_intent_per_user_kind",
              ),
          ]

  class CryptoPaymentIntentFactory(factory.django.DjangoModelFactory):
      initiator = factory.SubFactory("apps.users.tests.factories.SystemUserFactory")
      purchase_kind = PaymentKindEnum.SUBSCRIPTION
      product_code = ProductCodeEnum.MTPROTO_30D
      rub_amount = Decimal("99.00")
      status = CryptoPaymentIntentStatusEnum.CREATING

      class Meta:
          model = CryptoPaymentIntent

  models.UniqueConstraint(
      fields=("provider", "charge_id", "kind"),
      condition=models.Q(provider=PaymentProviderEnum.CRYPTO_PAY),
      name="uniq_crypto_payment_identity",
  )
  ```

- [ ] **RED selectors/admin.** Add named tests for reusable active lookup,
  expired exclusion, unfinished status set, unnotified fulfilled lookup,
  compare-and-set row count, identity lookup, subscription Payment creation and
  admin flags
  `has_add_permission=False`, `has_delete_permission=False`, no actions and all
  fields readonly. Dedicated transition tests prove that fulfillment claim also
  requires `payment_id IS NULL`, finalize links exactly one Payment, retryable
  marking cannot overwrite `FULFILLED`, provider expiry accepts only
  `ACTIVE|LOCAL_EXPIRED`, and notification timestamp updates only a fulfilled,
  previously unnotified row.

  ```python
  def test_claim_requires_unpaid_eligible_status(self) -> None:
      intent = CryptoPaymentIntentFactory(
          status=CryptoPaymentIntentStatusEnum.ACTIVE,
          payment=None,
      )
      self.assertEqual(
          claim_crypto_intent_for_fulfillment(
              intent_id=intent.pk,
              attempted_at=timezone.now(),
          ),
          1,
      )
      intent.refresh_from_db()
      self.assertEqual(intent.status, CryptoPaymentIntentStatusEnum.PROCESSING)
      self.assertEqual(
          claim_crypto_intent_for_fulfillment(
              intent_id=intent.pk,
              attempted_at=timezone.now(),
          ),
          0,
      )

  def test_crypto_admin_has_no_write_surface(self) -> None:
      model_admin = CryptoPaymentIntentAdmin(CryptoPaymentIntent, admin.site)
      request = RequestFactory().get("/admin/payments/cryptopaymentintent/")
      self.assertFalse(model_admin.has_add_permission(request))
      self.assertFalse(model_admin.has_change_permission(request))
      self.assertFalse(model_admin.has_delete_permission(request))
      self.assertEqual(model_admin.actions, None)

  def test_create_subscription_payment_records_identity_and_key(self) -> None:
      user = SystemUserFactory()
      key = MTPRotoKeyFactory(user=user)
      payment = create_subscription_payment(
          user_id=user.pk,
          key_id=key.pk,
          charge_id="invoice-41",
          provider=PaymentProviderEnum.CRYPTO_PAY,
      )
      self.assertEqual(payment.kind, PaymentKindEnum.SUBSCRIPTION)
      self.assertEqual(payment.key_id, key.pk)
  ```

- [ ] **Minimal selectors/admin GREEN.** Implement only the signatures above;
  queryset reads use `select_related` needed by their named consumer, conditional
  transition uses filtered `QuerySet.update`, and admin only lists/searches/
  filters architecture-approved diagnostic fields.

  ```python
  def claim_crypto_intent_for_fulfillment(
      *, intent_id: int, attempted_at: datetime
  ) -> int:
      return CryptoPaymentIntent.objects.filter(
          pk=intent_id,
          payment__isnull=True,
          status__in=(
              CryptoPaymentIntentStatusEnum.ACTIVE,
              CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
              CryptoPaymentIntentStatusEnum.RETRYABLE,
          ),
      ).update(
          status=CryptoPaymentIntentStatusEnum.PROCESSING,
          fulfillment_attempted_at=attempted_at,
          updated_at=attempted_at,
      )

  def create_subscription_payment(
      *, user_id: int, key_id: int, charge_id: str, provider: str
  ) -> Payment:
      return Payment.objects.create(
          user_id=user_id,
          key_id=key_id,
          charge_id=charge_id,
          provider=provider,
          kind=PaymentKindEnum.SUBSCRIPTION,
      )

  def reserve_crypto_intent_or_read_winner(
      *, initiator_id: int, purchase_kind: str, product_code: str,
      rub_amount: Decimal, public_id: UUID,
  ) -> tuple[CryptoPaymentIntent, bool]:
      try:
          with transaction.atomic():
              intent = CryptoPaymentIntent.objects.create(
                  public_id=public_id,
                  initiator_id=initiator_id,
                  purchase_kind=purchase_kind,
                  product_code=product_code,
                  rub_amount=rub_amount,
                  status=CryptoPaymentIntentStatusEnum.CREATING,
              )
          return intent, True
      except IntegrityError:
          winner = CryptoPaymentIntent.objects.filter(
              initiator_id=initiator_id,
              purchase_kind=purchase_kind,
              status__in=(
                  CryptoPaymentIntentStatusEnum.CREATING,
                  CryptoPaymentIntentStatusEnum.ACTIVE,
              ),
          ).first()
          if winner is None:
              raise
          return winner, False

  @admin.register(CryptoPaymentIntent)
  class CryptoPaymentIntentAdmin(admin.ModelAdmin):
      actions = None
      list_filter = ("status", "purchase_kind")
      search_fields = ("public_id", "provider_invoice_id")

      def has_add_permission(self, request: HttpRequest) -> bool:
          return False

      def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
          return False

      def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
          return False

      def get_readonly_fields(self, request: HttpRequest, obj=None) -> tuple[str, ...]:
          return tuple(field.name for field in self.model._meta.fields)
  ```

- [ ] **Verify task.** Run:

  ```bash
  make test ARGS="apps.payments.tests.test_crypto_models apps.payments.tests.test_crypto_selectors apps.payments.tests.test_crypto_migrations apps.payments.tests.test_crypto_admin apps.payments.tests.test_models apps.payments.tests.test_migrations"
  cd src && python manage.py makemigrations --check --dry-run --settings=config.test_settings
  ```

  Expected: PASS and `No changes detected`.

**Documentation:** model/admin docstrings only; global docs are reserved for
CPAY-009.

**Completion criterion:** migration is additive, legacy rows/duplicate
subscription behavior survive, both partial uniqueness rules fail only in their
approved conditions, selectors have the fixed signatures, and admin cannot add,
edit, delete or run actions.

**Task packet CPAY-B1:** `scope_revision: 2`; ID `CPAY-001`; allowed files are
the 10 files above; forbidden adjacent work is client/API/tasks/bot/docs,
generic Payment refactor and mark-paid action; non-goals are all Global
Constraints non-goals; budget ≤10 files and ≤700 changed lines including tests
and migration; complete only on targeted GREEN, migration check and independent
read-only review. Root alone may create the post-review commit checkpoint.

---

### CPAY-002 — Add exact DTOs, backend-only settings and thin Crypto Pay client

**Result:** a fully mocked provider boundary creates fiat RUB invoices and
retrieves invoice batches with decimal/time-safe strict parsing, fixed assets/
expiry and no PII or new dependency.

**Traceability:** BR-002..BR-004, BR-007, BR-010; AC-003, AC-010. Technical
assignment: architecture sections 2, 3, 8 and 10.

**Dependencies:** CPAY-001 targeted GREEN and approved batch review.

**Files and ownership:**

- Create: `src/apps/payments/clients/__init__.py`,
  `src/apps/payments/clients/crypto_pay.py`,
  `src/apps/payments/services/dtos/crypto_pay_dtos.py`.
- Modify: `src/apps/payments/services/dtos/__init__.py`,
  `src/apps/payments/exceptions.py`, `src/config/settings/payments.py`,
  `src/apps/payments/tests/factories.py`.
- Create/Test: `src/apps/payments/tests/test_crypto_pay_client.py`,
  `test_crypto_pay_dtos.py`, `test_crypto_pay_settings.py`.
- No model/selector/API/task/bot/docs/env-example changes in this batch.

**Interfaces:** produces every DTO and `CryptoPayClient` signature in “Interfaces
Shared Across Tasks”, plus `get_crypto_pay_client() -> CryptoPayClient`.
`CryptoPayClient` fields are exactly `base_url: str`, `api_token: str`,
`timeout: float`; factory reads Django settings and rejects a missing token or
non-positive timeout with a safe `ImproperlyConfigured` message that names the
setting but never its value. The webhook view independently requires the
configured non-empty webhook secret before comparing the captured path.

- [ ] **RED DTO/client tests.** Add tests
  `test_create_invoice_sends_exact_fiat_payload_without_pii`,
  `test_create_invoice_parses_decimal_and_aware_datetimes`,
  `test_get_invoices_sends_bounded_invoice_ids_and_maps_items`,
  `test_timeout_raises_crypto_pay_client_error_without_token_or_body`,
  `test_ok_false_raises_safe_error`, `test_malformed_result_raises_safe_error`,
  `test_non_object_envelope_raises_safe_malformed_error`, and DTO equality/type
  tests for all fixed fields.

  ```python
  VALID_INVOICE_JSON = {
      "invoice_id": 731, "status": "paid", "currency_type": "fiat",
      "fiat": "RUB", "amount": "99.00", "accepted_assets": "USDT,TON",
      "paid_asset": "USDT",
      "payload": "0f57a4f1-1956-45be-8dc0-d891c00c74c1",
      "bot_invoice_url": "https://t.me/CryptoBot?start=test",
      "created_at": "2026-08-02T12:00:00Z",
      "expiration_date": "2026-08-02T12:30:00Z",
      "paid_at": "2026-08-02T12:20:00Z",
  }

  @responses.activate
  def test_create_invoice_sends_exact_fiat_payload_without_pii(self) -> None:
      responses.post(
          "https://testnet-pay.crypt.bot/api/createInvoice",
          json={"ok": True, "result": VALID_INVOICE_JSON},
      )
      result = self.client.create_invoice(
          amount=Decimal("99.00"),
          payload="0f57a4f1-1956-45be-8dc0-d891c00c74c1",
          description="MTProto на 30 дней",
      )
      request = responses.calls[0].request
      self.assertEqual(request.headers["Crypto-Pay-API-Token"], "test-token")
      self.assertEqual(parse_qs(request.body), {
          "currency_type": ["fiat"], "fiat": ["RUB"],
          "amount": ["99.00"], "accepted_assets": ["USDT,TON"],
          "expires_in": ["1800"],
          "payload": ["0f57a4f1-1956-45be-8dc0-d891c00c74c1"],
          "description": ["MTProto на 30 дней"],
      })
      self.assertNotIn("telegram", request.body.lower())
      self.assertEqual(result.amount, Decimal("99.00"))
      self.assertTrue(timezone.is_aware(result.expiration_date))

  @responses.activate
  def test_non_object_envelope_raises_safe_malformed_error(self) -> None:
      for envelope in ([], None, "ok"):
          with self.subTest(envelope=envelope):
              responses.reset()
              responses.post(
                  "https://testnet-pay.crypt.bot/api/createInvoice",
                  json=envelope,
              )
              with self.assertRaisesRegex(
                  CryptoPayClientError, "^cryptopay_malformed$",
              ):
                  self.client.create_invoice(
                      amount=Decimal("99.00"),
                      payload="0f57a4f1-1956-45be-8dc0-d891c00c74c1",
                      description="MTProto на 30 дней",
                  )
  ```

  | Provider behavior | Expected safe exception |
  |---|---|
  | `requests.Timeout` | `CryptoPayClientError("cryptopay_timeout")` |
  | connection error/5xx | `CryptoPayClientError("cryptopay_unavailable")` |
  | valid JSON top-level `[]`, `null` or string | `CryptoPayClientError("cryptopay_malformed")` |
  | `{"ok": false}` | `CryptoPayClientError("cryptopay_rejected")` |
  | missing/ill-typed result field | `CryptoPayClientError("cryptopay_malformed")` |
  | timestamp is not a string, including Unix integer | `CryptoPayClientError("cryptopay_malformed")` |
  | timestamp is malformed or has no timezone offset | `CryptoPayClientError("cryptopay_malformed")` |

  Add this exact reusable test helper to `apps.payments.tests.factories` so
  later task tests reference a defined callable:

  ```python
  def make_crypto_invoice(
      *, invoice_id: int = 731, status: str = "paid",
      currency_type: str = "fiat", fiat: str | None = "RUB",
      amount: Decimal = Decimal("99.00"),
      accepted_assets: frozenset[str] = frozenset({"USDT", "TON"}),
      paid_asset: str | None = "USDT",
      payload: str = "0f57a4f1-1956-45be-8dc0-d891c00c74c1",
      bot_invoice_url: str = "https://t.me/CryptoBot?start=test",
      created_at: datetime = datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
      expiration_date: datetime = datetime(2026, 8, 2, 12, 30, tzinfo=UTC),
      paid_at: datetime | None = datetime(2026, 8, 2, 12, 20, tzinfo=UTC),
  ) -> CryptoInvoiceDTO:
      return CryptoInvoiceDTO(
          invoice_id=invoice_id, status=status, currency_type=currency_type,
          fiat=fiat, amount=amount, accepted_assets=accepted_assets,
          paid_asset=paid_asset, payload=payload,
          bot_invoice_url=bot_invoice_url, created_at=created_at,
          expiration_date=expiration_date, paid_at=paid_at,
      )
  ```

- [ ] **Run RED.** From root:

  ```bash
  make test ARGS="apps.payments.tests.test_crypto_pay_client apps.payments.tests.test_crypto_pay_dtos apps.payments.tests.test_crypto_pay_settings"
  ```

  Expected: import failures for `apps.payments.clients`, DTOs and Crypto settings.

- [ ] **Minimal client GREEN.** Use `requests.post` to
  `{base_url}/api/createInvoice` with header `Crypto-Pay-API-Token`; JSON/form
  fields are exactly:

  ```python
  {
      "currency_type": "fiat",
      "fiat": "RUB",
      "amount": format(amount, ".2f"),
      "accepted_assets": "USDT,TON",
      "expires_in": 1800,
      "payload": payload,
      "description": description,
  }
  ```

  Use `requests.get` for `{base_url}/api/getInvoices` with comma-separated
  `invoice_ids`. Both calls pass the configured timeout, require `ok is True`,
  parse exact DTO fields and raise only safe `CryptoPayClientError` values.

  ```python
  @final
  @dataclass(kw_only=True, slots=True, frozen=True)
  class CryptoPayClient:
      base_url: str
      api_token: str
      timeout: float

      def create_invoice(
          self, *, amount: Decimal, payload: str, description: str
      ) -> CryptoInvoiceDTO:
          result = self._request_json(
              method="POST",
              endpoint="createInvoice",
              data={
                  "currency_type": "fiat", "fiat": "RUB",
                  "amount": format(amount, ".2f"),
                  "accepted_assets": "USDT,TON", "expires_in": 1800,
                  "payload": payload, "description": description,
              },
          )
          return self._to_invoice(item=result)

      def get_invoices(self, *, invoice_ids: list[int]) -> list[CryptoInvoiceDTO]:
          result = self._request_json(
              method="GET", endpoint="getInvoices",
              data={"invoice_ids": ",".join(map(str, invoice_ids))},
          )
          items = result.get("items")
          if not isinstance(items, list):
              raise CryptoPayClientError("cryptopay_malformed")
          return [self._to_invoice(item=item) for item in items]

      def _request_json(self, *, method: str, endpoint: str, data: dict) -> dict:
          try:
              response = requests.request(
                  method,
                  f"{self.base_url.rstrip('/')}/api/{endpoint}",
                  headers={"Crypto-Pay-API-Token": self.api_token},
                  data=data,
                  timeout=self.timeout,
              )
              response.raise_for_status()
              envelope = response.json()
          except requests.Timeout as exc:
              raise CryptoPayClientError("cryptopay_timeout") from exc
          except (requests.RequestException, ValueError) as exc:
              raise CryptoPayClientError("cryptopay_unavailable") from exc
          if not isinstance(envelope, dict):
              raise CryptoPayClientError("cryptopay_malformed")
          if envelope.get("ok") is not True:
              raise CryptoPayClientError("cryptopay_rejected")
          result = envelope.get("result")
          if not isinstance(result, dict):
              raise CryptoPayClientError("cryptopay_malformed")
          return result
  ```

  `_to_invoice` constructs the exact `CryptoInvoiceDTO` declared globally with
  `Decimal(str(item["amount"]))`, the parser below for all three provider
  timestamps, and `frozenset(item["accepted_assets"].split(","))`; it catches
  key/type/decimal/time errors and raises
  `CryptoPayClientError("cryptopay_malformed")`. `created_at` and
  `expiration_date` must be non-null strings; `paid_at` alone may be `None`.

  ```python
  def _parse_provider_datetime(
      *, value: object, allow_none: bool = False,
  ) -> datetime | None:
      if value is None and allow_none:
          return None
      if not isinstance(value, str):
          raise CryptoPayClientError("cryptopay_malformed")
      normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
      try:
          parsed = datetime.fromisoformat(normalized)
      except ValueError as exc:
          raise CryptoPayClientError("cryptopay_malformed") from exc
      if parsed.tzinfo is None or parsed.utcoffset() is None:
          raise CryptoPayClientError("cryptopay_malformed")
      return parsed
  ```

  The malformed tests pass an integer for `created_at`, a naive ISO value for
  `expiration_date`, and a non-date string for `paid_at`; every case must raise
  the same safe malformed error. `_to_invoice` calls the helper with
  `allow_none=True` only for `paid_at`, so an active create response remains
  representable while every non-null DTO timestamp is timezone-aware.

- [ ] **Minimal settings GREEN.** Define exact settings with no secret default
  values: `CRYPTOPAY_API_TOKEN`, `CRYPTOPAY_WEBHOOK_SECRET` default to empty;
  `CRYPTOPAY_BASE_URL` defaults to `https://pay.crypt.bot` and accepts
  `https://testnet-pay.crypt.bot`; `CRYPTOPAY_REQUEST_TIMEOUT` is a positive
  float defaulting to `5.0`.

  ```python
  CRYPTOPAY_API_TOKEN = os.environ.get("CRYPTOPAY_API_TOKEN", "")
  CRYPTOPAY_BASE_URL = os.environ.get(
      "CRYPTOPAY_BASE_URL", "https://pay.crypt.bot",
  )
  CRYPTOPAY_WEBHOOK_SECRET = os.environ.get("CRYPTOPAY_WEBHOOK_SECRET", "")
  CRYPTOPAY_REQUEST_TIMEOUT = float(
      os.environ.get("CRYPTOPAY_REQUEST_TIMEOUT", "5"),
  )

  def get_crypto_pay_client() -> CryptoPayClient:
      if not settings.CRYPTOPAY_API_TOKEN:
          raise ImproperlyConfigured("CRYPTOPAY_API_TOKEN is required")
      if settings.CRYPTOPAY_REQUEST_TIMEOUT <= 0:
          raise ImproperlyConfigured("CRYPTOPAY_REQUEST_TIMEOUT must be positive")
      return CryptoPayClient(
          base_url=settings.CRYPTOPAY_BASE_URL,
          api_token=settings.CRYPTOPAY_API_TOKEN,
          timeout=settings.CRYPTOPAY_REQUEST_TIMEOUT,
      )
  ```

- [ ] **Exports and verification.** Explicitly export the client/factory and all
  DTOs, then run the RED command again plus:

  ```python
  # apps/payments/clients/__init__.py
  from apps.payments.clients.crypto_pay import CryptoPayClient, get_crypto_pay_client

  __all__ = ["CryptoPayClient", "get_crypto_pay_client"]
  ```

  ```bash
  make test ARGS="apps.payments.tests.test_crypto_pay_client apps.payments.tests.test_crypto_pay_dtos apps.payments.tests.test_crypto_pay_settings"
  python -m compileall -q src/apps/payments src/config/settings
  ```

**Documentation:** class/DTO/exception docstrings only; `.env.example` and
global docs belong to CPAY-009.

**Completion criterion:** `responses` proves exact provider request fields,
headers, timeout, decimal/timestamp mapping, safe malformed/error handling and
absence of username/Telegram ID/email; no dependency or bot setting is added.

**Task packet CPAY-B2:** `scope_revision: 2`; ID `CPAY-002`; allowed files are
the 10 files above; forbidden work is persistence, orchestration, endpoints,
Celery, bot, env/deploy/docs and provider abstractions; budget ≤10 files and ≤700
changed lines; complete on exact HTTP tests, compile check and independent
read-only review, followed only by root’s commit checkpoint.

---

### CPAY-003 — Create/reuse invoice service and BotAuth API

**Result:** all three purchase kinds use one protected endpoint that maps kind
to backend product, snapshots exact kopecks→RUB, reuses only a live active
invoice, safely recovers stale creating leases and returns the four exact fields.

**Traceability:** BR-002..BR-004, BR-007, BR-010..BR-011; AC-002..AC-004,
AC-010..AC-011.

**Dependencies:** CPAY-001 and CPAY-002 approved batch reviews.

**Files and ownership:**

- Create: `src/apps/payments/services/create_crypto_invoice.py`,
  `src/apps/payments/api/v1/serializers/crypto_pay_serializers.py`,
  `src/apps/payments/api/v1/views/crypto_pay_views.py`.
- Modify: `src/apps/payments/services/__init__.py`, serializer/view
  `__init__.py`, `src/apps/payments/api/v1/urls.py`.
- Create/Test: `src/apps/payments/tests/test_create_crypto_invoice_service.py`,
  `test_create_crypto_invoice_concurrency.py`,
  `tests/test_views/test_crypto_invoice_view.py`.
- Ownership excludes webhook code (same view module reserved section remains
  untouched until CPAY-005), fulfillment/tasks, bot and global docs.

**Interfaces:** consumes CPAY-001 selectors and CPAY-002 client/DTO; produces
`CreateOrReuseCryptoInvoiceService` and
`get_create_or_reuse_crypto_invoice_service()`. New contract is exactly:

```text
POST /api/v1/payments/crypto/invoices/
Bot-Auth-Token: existing backend token
username=<telegram id>&purchase_kind=subscription|vpn_subscription|gift_certificate

200 application/json
{"invoice_url":"https://t.me/CryptoBot?start=example","rub_amount":"99.00",
 "expires_at":"2026-08-02T12:30:00Z","reused":false}
```

- [ ] **RED service tests.** Add exact tests for 9900→`Decimal("99.00")`,
  14900→`Decimal("149.00")`, gift→`mtproto_30d`, active reuse with zero provider
  calls and identical stored output, local expiry→new snapshot, inactive/missing/
  non-RUB/non-positive/non-integral-kopeck product rejection, provider failure→
  `CREATE_FAILED`, and stale `CREATING` lease equal to
  `2 * CRYPTOPAY_REQUEST_TIMEOUT` becoming retryable. Add
  `test_validated_create_response_activates_with_matching_positive_invoice_id`
  and `test_create_response_mismatch_fails_creating_intent_without_returning_url`;
  the first proves that provider ID `731` is the exact positive ID persisted on
  the activated intent, while the second covers every row in the validation
  table below.

  ```python
  def test_maps_kind_and_converts_kopecks_exactly(self) -> None:
      cases = (
          (PaymentKindEnum.SUBSCRIPTION, ProductCodeEnum.MTPROTO_30D, "9900", "99.00"),
          (PaymentKindEnum.VPN_SUBSCRIPTION, ProductCodeEnum.VPN_30D, "14900", "149.00"),
          (PaymentKindEnum.GIFT_CERTIFICATE, ProductCodeEnum.MTPROTO_30D, "9900", "99.00"),
      )
      for kind, product_code, kopecks, rubles in cases:
          with self.subTest(kind=kind):
              Product.objects.all().delete()
              CryptoPaymentIntent.objects.all().delete()
              self.client.reset_mock()
              ProductFactory(code=product_code, price=Decimal(kopecks), currency="RUB")
              result = self.service(request=CreateCryptoInvoiceIn(
                  username=self.user.username, purchase_kind=kind,
              ))
              self.assertEqual(result.rub_amount, Decimal(rubles))
              self.assertEqual(
                  self.client.create_invoice.call_args.kwargs["amount"],
                  Decimal(rubles),
              )
              payload = self.client.create_invoice.call_args.kwargs["payload"]
              self.assertEqual(payload, str(CryptoPaymentIntent.objects.get().public_id))

  def test_active_invoice_is_reused_without_provider_call(self) -> None:
      intent = CryptoPaymentIntentFactory(
          initiator=self.user,
          purchase_kind=PaymentKindEnum.SUBSCRIPTION,
          status=CryptoPaymentIntentStatusEnum.ACTIVE,
          provider_expires_at=self.now + timedelta(minutes=5),
          provider_invoice_url="https://t.me/CryptoBot?start=reuse",
          rub_amount=Decimal("99.00"),
      )
      result = self.service(request=CreateCryptoInvoiceIn(
          username=self.user.username,
          purchase_kind=PaymentKindEnum.SUBSCRIPTION,
      ))
      self.assertEqual(result.invoice_url, intent.provider_invoice_url)
      self.assertTrue(result.reused)
      self.client.create_invoice.assert_not_called()
  ```

  | Product/create state | Exact expectation |
  |---|---|
  | missing or inactive | `ProductNotFound(username)`; no intent/provider call |
  | currency != `RUB` | `BadPaymentData(username, reason_code="invalid_currency")` |
  | price ≤ 0 or fractional kopeck | `BadPaymentData(username, reason_code="invalid_price")` |
  | provider error | intent `CREATE_FAILED`, `last_error_code`, retryable infra error |
  | stale `CREATING` age ≥ `2 * timeout` | conditional `CREATE_FAILED`, new reservation allowed |

  | createInvoice response condition | Exact safe result before activation |
  |---|---|
  | `invoice_id` is not an `int` or is ≤ 0 | `create_invoice_id_invalid` |
  | `status != "active"` | `create_status_invalid` |
  | `payload != str(intent.public_id)` | `create_payload_mismatch` |
  | `currency_type != "fiat"` | `create_currency_type_mismatch` |
  | `fiat != "RUB"` | `create_fiat_mismatch` |
  | `amount !=` the exact requested `Decimal` | `create_amount_mismatch` |
  | `accepted_assets != frozenset({"USDT", "TON"})` | `create_assets_mismatch` |
  | either `paid_asset` or `paid_at` is non-null | `create_already_paid` |
  | URL is not a usable absolute HTTPS URL | `create_url_invalid` |
  | either created/expiration value is not timezone-aware | `create_timestamp_invalid` |
  | expiration is not later than creation | `create_expiration_invalid` |
  | expiration minus creation is not exactly 1800 seconds | `create_expiration_invalid` |

  For each mismatch, configure the mocked client from a valid active response
  built with `make_crypto_invoice(status="active", paid_asset=None,
  paid_at=None, amount=amount, payload=payload)` and change exactly the field in
  the table. Assert `CryptoInvoiceUnavailable(username,
  reason_code=<table code>)`, then reload the reserved row and assert status
  `CREATE_FAILED`, matching `last_error_code`, null `provider_invoice_id`, blank
  `provider_invoice_url`, and no `ACTIVE` row. The service call yields no output,
  so no provider URL can be returned. Use concrete invalid values `0`, `"731"`,
  `"paid"`, `"wrong-public-id"`, `"crypto"`, `"USD"`,
  `Decimal("99.01")`, `frozenset({"USDT"})`, `"USDT"`, an aware non-null
  `paid_at`, `"http://t.me/CryptoBot?start=test"`, a naive `created_at`, a naive
  `expiration_date`, equal created/expiration values, and an aware 1799-second
  lifetime. The valid companion test asserts `ACTIVE`, ID `731`, the same HTTPS
  URL, aware provider timestamps and the returned four-field output only after
  all checks pass.

- [ ] **Run service RED.** From root:

  ```bash
  make test ARGS="apps.payments.tests.test_create_crypto_invoice_service"
  ```

  Expected: missing service/factory; after its skeleton exists, expected failures
  are absent mapping/state transitions, never an unexpected DB lock.

- [ ] **Minimal service GREEN.** Implement the approved algorithm in order:
  lookup initiator; reuse `ACTIVE` with expiry `> now`; conditional local expiry;
  map kind to product; validate/convert price; reserve `CREATING`; perform provider
  call outside atomic; conditional promote to `ACTIVE`; on provider error mark
  `CREATE_FAILED`. On uniqueness loss reread winner: return `ACTIVE` as reused or
  raise safe retryable `CryptoInvoiceCreationInProgress` mapped to HTTP 409.

  ```python
  _PRODUCT_BY_KIND = {
      PaymentKindEnum.SUBSCRIPTION: ProductCodeEnum.MTPROTO_30D,
      PaymentKindEnum.VPN_SUBSCRIPTION: ProductCodeEnum.VPN_30D,
      PaymentKindEnum.GIFT_CERTIFICATE: ProductCodeEnum.MTPROTO_30D,
  }

  def _is_aware_datetime(value: object) -> bool:
      return (
          isinstance(value, datetime)
          and value.tzinfo is not None
          and value.utcoffset() is not None
      )

  def _is_usable_https_url(value: object) -> bool:
      if not isinstance(value, str):
          return False
      try:
          parsed = urlsplit(value)
          return (
              parsed.scheme == "https"
              and bool(parsed.netloc)
              and parsed.hostname is not None
          )
      except ValueError:
          return False

  def _created_invoice_error_code(
      *, invoice: CryptoInvoiceDTO, intent: CryptoPaymentIntent,
      requested_amount: Decimal,
  ) -> str | None:
      if type(invoice.invoice_id) is not int or invoice.invoice_id <= 0:
          return "create_invoice_id_invalid"
      if invoice.status != "active":
          return "create_status_invalid"
      if invoice.payload != str(intent.public_id):
          return "create_payload_mismatch"
      if invoice.currency_type != "fiat":
          return "create_currency_type_mismatch"
      if invoice.fiat != "RUB":
          return "create_fiat_mismatch"
      if invoice.amount != requested_amount:
          return "create_amount_mismatch"
      if invoice.accepted_assets != frozenset({"USDT", "TON"}):
          return "create_assets_mismatch"
      if invoice.paid_asset is not None or invoice.paid_at is not None:
          return "create_already_paid"
      if not _is_usable_https_url(invoice.bot_invoice_url):
          return "create_url_invalid"
      if not (
          _is_aware_datetime(invoice.created_at)
          and _is_aware_datetime(invoice.expiration_date)
      ):
          return "create_timestamp_invalid"
      if invoice.expiration_date <= invoice.created_at:
          return "create_expiration_invalid"
      if invoice.expiration_date - invoice.created_at != timedelta(seconds=1800):
          return "create_expiration_invalid"
      return None

  def __call__(self, *, request: CreateCryptoInvoiceIn) -> CreateCryptoInvoiceOut:
      now = self.clock()
      user = get_user_by_username(username=request.username)
      if user is None or request.purchase_kind not in _PRODUCT_BY_KIND:
          raise BadPaymentData(request.username, reason_code="invalid_purchase")
      reusable = get_reusable_crypto_intent(
          initiator_id=user.pk, purchase_kind=request.purchase_kind, now=now,
      )
      if reusable is not None:
          return CreateCryptoInvoiceOut(
              invoice_url=reusable.provider_invoice_url,
              rub_amount=reusable.rub_amount,
              expires_at=reusable.provider_expires_at,
              reused=True,
          )
      expire_active_crypto_intent(
          initiator_id=user.pk, purchase_kind=request.purchase_kind, now=now,
      )
      fail_stale_creating_crypto_intent(
          initiator_id=user.pk,
          purchase_kind=request.purchase_kind,
          stale_before=now - timedelta(seconds=2 * settings.CRYPTOPAY_REQUEST_TIMEOUT),
      )
      product_code = _PRODUCT_BY_KIND[PaymentKindEnum(request.purchase_kind)]
      product = get_active_product_by_code(code=product_code)
      if product is None:
          raise ProductNotFound(request.username)
      kopecks = Decimal(product.price)
      if product.currency != "RUB":
          raise BadPaymentData(request.username, reason_code="invalid_currency")
      if kopecks <= 0 or kopecks != kopecks.to_integral_value():
          raise BadPaymentData(request.username, reason_code="invalid_price")
      amount = (kopecks / Decimal("100")).quantize(Decimal("0.01"))
      intent, created = reserve_crypto_intent_or_read_winner(
          initiator_id=user.pk,
          purchase_kind=request.purchase_kind,
          product_code=product_code,
          rub_amount=amount,
          public_id=uuid4(),
      )
      if not created:
          if (
              intent.status == CryptoPaymentIntentStatusEnum.ACTIVE
              and intent.provider_expires_at > now
          ):
              return _intent_output(intent=intent, reused=True)
          raise CryptoInvoiceCreationInProgress(
              request.username, reason_code="creating",
          )
      try:
          invoice = self.crypto_pay_client.create_invoice(
              amount=amount,
              payload=str(intent.public_id),
              description=product.title,
          )
      except CryptoPayClientError as exc:
          fail_crypto_intent_creation(intent_id=intent.pk, error_code=str(exc))
          raise CryptoInvoiceUnavailable(request.username, reason_code=str(exc)) from exc
      error_code = _created_invoice_error_code(
          invoice=invoice, intent=intent, requested_amount=amount,
      )
      if error_code is not None:
          fail_crypto_intent_creation(intent_id=intent.pk, error_code=error_code)
          raise CryptoInvoiceUnavailable(request.username, reason_code=error_code)
      activated = activate_crypto_intent_from_provider(intent_id=intent.pk, invoice=invoice)
      return _intent_output(intent=activated, reused=False)
  ```

  `fail_crypto_intent_creation` retains its CPAY-001 compare-and-set boundary:
  it changes only the still-`CREATING` row to `CREATE_FAILED`. The validator
  runs before `activate_crypto_intent_from_provider`; that selector therefore
  never receives or persists an invalid ID, URL or timestamp and never promotes
  an invalid response to `ACTIVE`.

  The additional selector names used here are implemented in CPAY-001 with the
  stated conditional-update semantics:
  `expire_active_crypto_intent`, `fail_stale_creating_crypto_intent`,
  `reserve_crypto_intent_or_read_winner`, `fail_crypto_intent_creation`, and
  `activate_crypto_intent_from_provider`.

- [ ] **RED API tests.** Add named tests
  `test_create_invoice_requires_bot_auth_token`,
  `test_create_invoice_rejects_unknown_kind`,
  `test_new_invoice_returns_exact_four_fields`,
  `test_reused_invoice_returns_same_values_and_reused_true`, and
  `test_provider_error_returns_safe_503_without_secret`.

  ```python
  @patch("apps.payments.api.v1.views.crypto_pay_views.get_create_or_reuse_crypto_invoice_service")
  def test_new_invoice_returns_exact_four_fields(self, get_service: Mock) -> None:
      get_service.return_value.return_value = CreateCryptoInvoiceOut(
          invoice_url="https://t.me/CryptoBot?start=invoice",
          rub_amount=Decimal("99.00"),
          expires_at=datetime(2026, 8, 2, 12, 30, tzinfo=UTC),
          reused=False,
      )
      response = self.client.post(
          reverse("crypto-invoice-create"),
          {"username": "1487189460", "purchase_kind": "subscription"},
          headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
      )
      self.assertEqual(response.status_code, 200)
      self.assertEqual(response.json(), {
          "invoice_url": "https://t.me/CryptoBot?start=invoice",
          "rub_amount": "99.00",
          "expires_at": "2026-08-02T12:30:00Z",
          "reused": False,
      })
  ```

- [ ] **Minimal API GREEN.** Request serializer accepts only `username` and the
  three `PaymentKindEnum` values. Response serializer uses
  `DecimalField(max_digits=10, decimal_places=2, coerce_to_string=True)`,
  `DateTimeField` and `BooleanField`; view uses `BotAuthToken`, returns 200 for
  both new/reused, 409 for live create contention and 502/503 only for safe
  provider failures.

  ```python
  class CreateCryptoInvoiceRequestSerializer(serializers.Serializer):
      username = serializers.CharField()
      purchase_kind = serializers.ChoiceField(choices=PaymentKindEnum.choices())

  class CreateCryptoInvoiceResponseSerializer(serializers.Serializer):
      invoice_url = serializers.URLField()
      rub_amount = serializers.DecimalField(
          max_digits=10, decimal_places=2, coerce_to_string=True,
      )
      expires_at = serializers.DateTimeField()
      reused = serializers.BooleanField()

  class CreateCryptoInvoiceView(APIView):
      permission_classes = (BotAuthToken,)
      http_method_names = ["post"]

      def post(self, request: Request) -> Response:
          incoming = CreateCryptoInvoiceRequestSerializer(data=request.data)
          incoming.is_valid(raise_exception=True)
          result = get_create_or_reuse_crypto_invoice_service()(
              request=CreateCryptoInvoiceIn(**incoming.validated_data),
          )
          outgoing = CreateCryptoInvoiceResponseSerializer(instance=result)
          return Response(outgoing.data, status=status.HTTP_200_OK)
  ```

- [ ] **Concurrency proof.** In `TransactionTestCase`, two barrier-synchronized
  requests for one user/kind must leave exactly one `CREATING` or `ACTIVE`
  intent. Run:

  ```python
  def test_two_requests_leave_one_live_reservation(self) -> None:
      barrier = Barrier(2)

      def create() -> int:
          close_old_connections()
          barrier.wait()
          try:
              self.service(request=self.request)
          except CryptoInvoiceCreationInProgress:
              return 409
          return 200

      with ThreadPoolExecutor(max_workers=2) as pool:
          statuses = list(pool.map(lambda _: create(), range(2)))
      self.assertIn(200, statuses)
      self.assertTrue(all(status in {200, 409} for status in statuses))
      self.assertEqual(CryptoPaymentIntent.objects.filter(
          initiator=self.user,
          purchase_kind=PaymentKindEnum.SUBSCRIPTION,
          status__in=("creating", "active"),
      ).count(), 1)
  ```

  ```bash
  make test ARGS="apps.payments.tests.test_create_crypto_invoice_service apps.payments.tests.test_create_crypto_invoice_concurrency apps.payments.tests.test_views.test_crypto_invoice_view"
  ```

**Documentation:** API/service docstrings in this task; contract docs in
CPAY-009.

**Completion criterion:** three kinds map to approved products; provider gets
exact RUB/assets/expiry/opaque payload without PII; reuse/new response is exact
and decimal-safe; create failures can be retried; concurrent requests cannot
leave two active reservations.

**Task packet CPAY-B3:** `scope_revision: 2`; ID `CPAY-003`; allowed files are
the 10 paths/groups above; forbidden work is webhook/apply/tasks/bot/docs,
arbitrary kind→product input and network calls inside a write transaction;
budget ≤10 files and ≤850 changed lines; completion requires targeted service,
API and TransactionTestCase GREEN plus independent read-only review and root-only
commit checkpoint.

---

### CPAY-004 — Exact-once fulfillment and durable post-commit user result

**Result:** one conditional SQLite-safe claim fulfills MTProto, VPN or gift for
the intent initiator exactly once, stores the resulting Payment atomically, and
reliably enqueues the approved Telegram result only after commit.

**Traceability:** BR-005..BR-006, BR-008, BR-010; AC-005..AC-006, AC-008..AC-009.
Technical assignment: architecture sections 2 and 5.

**Dependencies:** CPAY-003 approved batch review. May run in parallel only with
CPAY-B7.

**Files and ownership:**

- Create: `src/apps/payments/services/apply_crypto_payment.py`,
  `src/apps/payments/tasks.py`,
  `src/apps/notifications/migrations/0011_seed_crypto_purchase_templates.py`.
- Modify: `src/apps/payments/services/create_payment_service.py`,
  `src/apps/payments/services/__init__.py`.
- Create/Test: `src/apps/payments/tests/test_apply_crypto_payment_service.py`,
  `test_crypto_notification_task.py`,
  `src/apps/notifications/tests/test_crypto_purchase_templates_migration.py`.
- Modify/Test: `src/apps/payments/tests/test_create_payment_service.py`.
- No webhook/reconciliation/API/bot/docs edits.

**Interfaces:** consumes `ValidatedCryptoPaymentDTO`, CPAY-001 conditional
selectors, `CreatePaymentService`, `FulfillVPNPurchaseService` and
`CreateGiftCertificateService`. Produces `ApplyCryptoPaymentService`,
`get_apply_crypto_payment_service()`, `ApplyCryptoPaymentOut` and
`notify_crypto_purchase_task(intent_id: int)`.

The only backward-compatible MTProto signature change is:

```python
def __call__(
    self, *, payment: CreatePaymentIn, send_success_notification: bool = True
) -> None:
```

`CreatePaymentService` also receives injected `IssueKeyService`; its factory
uses `get_issue_key_on_commit_service()` so existing Stars behavior is unchanged
outside an outer transaction while Crypto push is deferred until the outer
commit. Crypto calls it with `send_success_notification=False`.

- [ ] **RED compatibility tests.** Add assertions that default MTProto calls
  still notify once, `send_success_notification=False` never sends directly,
  issue-key push is absent before commit and runs after commit. Run:

  ```python
  def test_crypto_can_disable_direct_success_notification(self) -> None:
      notifier = mock.Mock()
      issue = mock.Mock(return_value=MTPRotoKeyFactory(user=self.user))
      service = CreatePaymentService(
          extend_key_service=get_extend_key_service(),
          issue_key_service=issue,
          notify_success=notifier,
      )
      service(payment=self._make_payment(), send_success_notification=False)
      notifier.assert_not_called()

  def test_default_notification_and_issue_push_run_after_commit(self) -> None:
      with self.captureOnCommitCallbacks(execute=False) as callbacks:
          self.service(payment=self._make_payment())
          self.assertEqual(self.notifier.call_count, 1)
          self.assertEqual(self.mock_push.call_count, 0)
      for callback in callbacks:
          callback()
      self.mock_push.assert_called_once()
  ```

  ```bash
  make test ARGS="apps.payments.tests.test_create_payment_service"
  ```

  Expected: unexpected keyword/constructor errors and current pre-commit push.

- [ ] **Minimal compatible MT change.** Inject issue service, preserve the
  default notification branch byte-for-byte in behavior, and skip it only when
  the explicit flag is false. Obtain GREEN before adding Crypto apply.

  ```python
  @final
  @dataclass(kw_only=True, slots=True, frozen=True)
  class CreatePaymentService:
      extend_key_service: ExtendKeyService
      issue_key_service: IssueKeyService
      notify_success: NotifyPaymentSuccess

      def __call__(
          self, *, payment: CreatePaymentIn,
          send_success_notification: bool = True,
      ) -> None:
          user = get_user_by_username(username=payment.username)
          if user is None:
              raise BadPaymentData(payment.username)
          with transaction.atomic():
              active_key = get_active_key(user=user)
              if active_key is None:
                  key = self.issue_key_service(
                      user=user,
                      expired_date=timezone.now() + timedelta(
                          days=settings.SUBSCRIPTION_PERIOD_DAYS,
                      ),
                  )
              else:
                  self.extend_key_service(key=active_key)
                  key = active_key
              create_subscription_payment(
                  user_id=user.pk,
                  key_id=key.pk,
                  charge_id=payment.charge_id,
                  provider=payment.provider,
              )
          if send_success_notification:
              try:
                  self.notify_success(
                      chat_id=int(user.username),
                      expired_date=key.expired_date.date().strftime("%d.%m.%y"),
                  )
              except Exception:
                  pass  # preserves current best-effort Stars behavior

  def _notify_payment_success(*, chat_id: int, expired_date: str) -> None:
      SendNotificationService(
          slug="proxy_purchased",
          context={"expired_date": expired_date},
      )(chat_id=chat_id)

  def get_create_payment_service() -> CreatePaymentService:
      return CreatePaymentService(
          extend_key_service=get_extend_key_service(),
          issue_key_service=get_issue_key_on_commit_service(),
          notify_success=_notify_payment_success,
      )
  ```

- [ ] **RED exact-once tests.** Add per-kind issue/extend/create cases, owner is
  `intent.initiator` irrespective of provider payload, delayed paid invoice from
  `LOCAL_EXPIRED`, duplicate returns `already_fulfilled=True`, concurrent claim
  creates one product/Payment, `PROCESSING` returns retryable error, domain/
  SQLite failure rolls back product+Payment+claim then marks `RETRYABLE`, and no
  notification/provisioning callback runs before commit.

  ```python
  def test_valid_payment_fulfills_once_for_intent_owner(self) -> None:
      cases = (
          (PaymentKindEnum.SUBSCRIPTION, "create_payment_service"),
          (PaymentKindEnum.VPN_SUBSCRIPTION, "fulfill_vpn_purchase_service"),
          (PaymentKindEnum.GIFT_CERTIFICATE, "create_gift_certificate_service"),
      )
      for offset, (kind, dependency_name) in enumerate(cases, start=1):
          with self.subTest(kind=kind):
              dependency = getattr(self.service, dependency_name)
              dependency.reset_mock()
              intent = CryptoPaymentIntentFactory(
                  initiator=self.initiator, purchase_kind=kind,
                  status=CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
                  provider_invoice_id=730 + offset,
                  provider_expires_at=datetime(2026, 8, 2, 12, 30, tzinfo=UTC),
              )
              validated = ValidatedCryptoPaymentDTO(
                  intent_id=intent.pk,
                  invoice=make_crypto_invoice(
                      invoice_id=730 + offset,
                      paid_at=intent.provider_expires_at,
                  ),
              )
              with self.captureOnCommitCallbacks(execute=True):
                  result = self.service(payment=validated)
              self.assertTrue(result.fulfilled)
              kwargs = dependency.call_args.kwargs
              domain_dto = kwargs.get("payment") or kwargs["certificate"]
              self.assertEqual(domain_dto.username, self.initiator.username)
              duplicate = self.service(payment=validated)
              self.assertTrue(duplicate.already_fulfilled)
              self.assertEqual(dependency.call_count, 1)
  ```

  | Starting condition | Exact result |
  |---|---|
  | `ACTIVE`, `LOCAL_EXPIRED`, `RETRYABLE`, unpaid | one claim and fulfillment |
  | matching `FULFILLED` | `already_fulfilled=True`, no domain call |
  | `PROCESSING` | `CryptoPaymentRetryable(initiator.username, reason_code="processing")` |
  | SQLite lock/domain temporary failure | atomic rollback, then `RETRYABLE`, exception re-raised |

- [ ] **Minimal apply GREEN.** Inside one `transaction.atomic()`, conditional
  update `ACTIVE|LOCAL_EXPIRED|RETRYABLE` and `payment_id IS NULL` to
  `PROCESSING`; only row-count 1 calls the mapped existing service with
  `username=intent.initiator.username`, `provider="crypto_pay"`,
  `charge_id=str(invoice.invoice_id)` and VPN product snapshot. Lookup resulting
  Payment, set `paid_at`, `payment`, `fulfilled_at`, status `FULFILLED`, clear
  error and register `notify_crypto_purchase_task.delay(intent_id)` via
  `transaction.on_commit`. After rollback, a short conditional update records
  `RETRYABLE`/safe code and re-raises a retryable exception.

  ```python
  def __call__(self, *, payment: ValidatedCryptoPaymentDTO) -> ApplyCryptoPaymentOut:
      intent = get_crypto_intent_by_id(intent_id=payment.intent_id)
      if intent is None:
          raise CryptoPaymentRetryable("0", reason_code="intent_missing")
      try:
          with transaction.atomic():
              claimed = claim_crypto_intent_for_fulfillment(
                  intent_id=intent.pk, attempted_at=self.clock(),
              )
              if claimed == 0:
                  current = get_crypto_intent_by_id(intent_id=intent.pk)
                  if current is not None and current.status == CryptoPaymentIntentStatusEnum.FULFILLED:
                      return ApplyCryptoPaymentOut(fulfilled=False, already_fulfilled=True)
                  raise CryptoPaymentRetryable(
                      intent.initiator.username, reason_code="processing",
                  )
              charge_id = str(payment.invoice.invoice_id)
              if intent.purchase_kind == PaymentKindEnum.SUBSCRIPTION:
                  self.create_payment_service(
                      payment=CreatePaymentIn(
                          username=intent.initiator.username,
                          charge_id=charge_id,
                          provider=PaymentProviderEnum.CRYPTO_PAY,
                      ),
                      send_success_notification=False,
                  )
              elif intent.purchase_kind == PaymentKindEnum.VPN_SUBSCRIPTION:
                  self.fulfill_vpn_purchase_service(payment=FulfillVPNPaymentIn(
                      username=intent.initiator.username,
                      charge_id=charge_id,
                      provider=PaymentProviderEnum.CRYPTO_PAY,
                      product_code=intent.product_code,
                  ))
              else:
                  self.create_gift_certificate_service(
                      certificate=CreateGiftCertificateIn(
                          username=intent.initiator.username,
                          charge_id=charge_id,
                          provider=PaymentProviderEnum.CRYPTO_PAY,
                      ),
                  )
              stored = get_payment_by_identity(
                  provider=PaymentProviderEnum.CRYPTO_PAY,
                  charge_id=str(payment.invoice.invoice_id),
                  kind=intent.purchase_kind,
              )
              if stored is None:
                  raise CryptoPaymentRetryable(
                      intent.initiator.username, reason_code="payment_missing",
                  )
              if payment.invoice.paid_at is None:
                  raise CryptoPaymentRetryable(
                      intent.initiator.username, reason_code="paid_at_missing",
                  )
              finalize_crypto_intent_fulfillment(
                  intent_id=intent.pk,
                  payment_id=stored.pk,
                  paid_at=payment.invoice.paid_at,
                  fulfilled_at=self.clock(),
              )
              transaction.on_commit(
                  lambda: self.enqueue_notification(intent_id=intent.pk),
              )
              return ApplyCryptoPaymentOut(fulfilled=True, already_fulfilled=False)
      except (OperationalError, CryptoPaymentRetryable):
          mark_crypto_intent_retryable(
              intent_id=intent.pk, error_code="fulfillment_retryable",
          )
          raise
  ```

- [ ] **RED/GREEN durable notification.** Seed only
  `crypto_vpn_purchased` and `crypto_gift_certificate_purchased`; MTProto uses
  existing `proxy_purchased`. The data migration uses `get_or_create` so it adds
  only missing templates and never edits Stars templates. Test task formats MT expiry, VPN `expired_at` +
  permanent `subscription_url`, or gift code, patches
  `apps.core.telegram.transport.send_telegram_message`, sets
  `notification_sent_at` only after successful send, and retries temporary
  Telegram errors without logging result secrets.

  ```python
  TEMPLATES = (
      {
          "slug": "crypto_vpn_purchased",
          "title": "Crypto Pay: результат VPN",
          "text": (
              "✅ <b>VPN-подписка активирована</b>\n\n"
              "Действует до: <b>{expired_at}</b>\n\n"
              "Subscription-ссылка:\n<code>{subscription_url}</code>"
          ),
      },
      {
          "slug": "crypto_gift_certificate_purchased",
          "title": "Crypto Pay: подарочный сертификат",
          "text": (
              "🎁 <b>Подарочный сертификат готов</b>\n\n"
              "Код: <code>{code}</code>"
          ),
      },
  )

  def forwards(apps, schema_editor) -> None:
      template_model = apps.get_model("notifications", "NotificationTemplate")
      for template in TEMPLATES:
          template_model.objects.get_or_create(slug=template["slug"], defaults=template)

  @override_settings(VPN_SUBSCRIPTION_BASE_URL="https://vpn.example")
  @patch("apps.notifications.services.send_notification_service.send_telegram_message")
  def test_vpn_notification_uses_exact_context_and_marks_after_send(self, send: Mock) -> None:
      subscription = VPNSubscriptionFactory()
      payment = PaymentFactory(
          user=subscription.user,
          kind=PaymentKindEnum.VPN_SUBSCRIPTION,
          provider=PaymentProviderEnum.CRYPTO_PAY,
      )
      intent = CryptoPaymentIntentFactory(
          initiator=subscription.user,
          purchase_kind=PaymentKindEnum.VPN_SUBSCRIPTION,
          status=CryptoPaymentIntentStatusEnum.FULFILLED,
          payment=payment,
          fulfilled_at=timezone.now(),
          notification_sent_at=None,
      )
      notify_crypto_purchase_task.run(intent.pk)
      text = send.call_args.kwargs["text"]
      self.assertIn(intent.payment.user.vpn_subscription.expired_at.strftime("%d.%m.%Y %H:%M UTC"), text)
      expected_url = (
          "https://vpn.example/api/v1/vpn/subscriptions/"
          f"{subscription.token}/"
      )
      self.assertIn(expected_url, text)
      intent.refresh_from_db()
      self.assertIsNotNone(intent.notification_sent_at)
  ```

  Exact task mapping is:

  | kind | template slug | context keys |
  |---|---|---|
  | `subscription` | existing `proxy_purchased` | `expired_date` (`%d.%m.%y`) |
  | `vpn_subscription` | `crypto_vpn_purchased` | `expired_at` (`%d.%m.%Y %H:%M UTC`), `subscription_url` |
  | `gift_certificate` | `crypto_gift_certificate_purchased` | `code` |

  `notify_crypto_purchase_task` loads the fulfilled unnotified intent through
  `get_crypto_intent_for_notification`, calls `SendNotificationService` with
  exactly the table entry, then calls
  `mark_crypto_notification_sent(intent_id=intent.pk, sent_at=timezone.now())`.
  It is `bind=True, max_retries=3`; a Telegram exception raises
  `self.retry(exc=exc, countdown=30)` and does not set the timestamp.

- [ ] **Verify task.** Run:

  ```bash
  make test ARGS="apps.payments.tests.test_create_payment_service apps.payments.tests.test_apply_crypto_payment_service apps.payments.tests.test_crypto_notification_task apps.notifications.tests.test_crypto_purchase_templates_migration apps.vpn.tests.test_fulfill_vpn_purchase_service apps.payments.tests.test_gift_certificates"
  ```

**Documentation:** service/task/template docstrings only; global docs deferred.

**Completion criterion:** every kind creates exactly one approved product and
Payment for the initiator, duplicate is no-op, rollback stays retryable, all
side effects are post-commit, Stars default remains green, and successful user
delivery alone sets `notification_sent_at`.

**Task packet CPAY-B4:** `scope_revision: 2`; ID `CPAY-004`; allowed files are
the 9 paths above; forbidden work is provider validation/webhook/admin warning,
reconciliation, bot/docs, changes inside VPN/gift domain services and Stars
contract changes; budget ≤9 files and ≤950 changed lines; completion requires
targeted regressions, independent review and root-only checkpoint. Parallelism
is permitted only with CPAY-B7 because file sets are disjoint.

---

### CPAY-005 — Authenticate webhook, validate semantics and warn admin safely

**Result:** public Django webhook verifies secret path and HMAC over exact raw
bytes before parsing, validates the invoice through one service, invokes apply,
and turns signed unknown/mismatch events into structured safe log + durable
admin-warning enqueue with the approved response semantics.

**Traceability:** BR-006..BR-007, BR-010, BR-012; AC-005..AC-007, AC-012.

**Dependencies:** CPAY-004 approved batch review. May run in parallel only with
CPAY-B8.

**Files and ownership:**

- Create: `src/apps/payments/services/validate_crypto_invoice.py`.
- Modify: `src/apps/payments/services/__init__.py`,
  `src/apps/payments/tasks.py`,
  `src/apps/payments/api/v1/serializers/crypto_pay_serializers.py`,
  `src/apps/payments/api/v1/views/crypto_pay_views.py`, serializer/view exports,
  `src/apps/payments/api/v1/urls.py`, `src/config/middlewares.py`.
- Create/Test: `src/apps/payments/tests/test_validate_crypto_invoice_service.py`,
  `tests/test_views/test_crypto_webhook_view.py`,
  `test_crypto_admin_warning_task.py`,
  `src/apps/core/tests/test_crypto_webhook_logging.py`.
- No create algorithm, apply algorithm, models/migration, bot or docs changes.

**Interfaces:** consumes CPAY-002 `CryptoInvoiceDTO`, CPAY-004 apply and warning
transport; produces the fixed `ValidateCryptoInvoiceService` union result,
`get_validate_crypto_invoice_service()` and
`warn_crypto_webhook_admin_task(warning: dict[str, int | str | None])`.
Contract:

```text
POST /api/v1/payments/crypto/webhooks/<CRYPTOPAY_WEBHOOK_SECRET>/
crypto-pay-api-signature: hex(HMAC-SHA256(SHA256(api_token), raw_body))
```

- [ ] **RED authentication tests.** Use a fixed raw JSON byte string and known
  HMAC vector. Assert wrong secret→404, absent/bad signature→401, valid HMAC
  fails if JSON is reserialized before hashing, malformed signed JSON→400, and
  no apply/log/admin enqueue occurs for any auth failure.

  ```python
  RAW_EVENT = b'{"update_id":42,"update_type":"invoice_paid","payload":{"invoice_id":731,"status":"paid"}}'

  def _signature(*, raw: bytes, token: str = "test-api-token") -> str:
      key = hashlib.sha256(token.encode()).digest()
      return hmac.new(key, raw, hashlib.sha256).hexdigest()

  @override_settings(
      CRYPTOPAY_API_TOKEN="test-api-token",
      CRYPTOPAY_WEBHOOK_SECRET="path-secret",
  )
  @patch("apps.payments.api.v1.views.crypto_pay_views.get_apply_crypto_payment_service")
  def test_hmac_is_checked_against_exact_raw_bytes(self, get_apply: Mock) -> None:
      response = self.client.generic(
          "POST",
          "/api/v1/payments/crypto/webhooks/path-secret/",
          RAW_EVENT,
          content_type="application/json",
          HTTP_CRYPTO_PAY_API_SIGNATURE=_signature(raw=RAW_EVENT),
      )
      self.assertNotEqual(response.status_code, 401)
      get_apply.assert_not_called()  # minimal payload is contract-invalid after auth
  ```

  | Request | Status | apply/warning |
  |---|---:|---|
  | wrong path secret | 404 | neither |
  | missing/bad HMAC | 401 | neither |
  | valid HMAC + malformed JSON | 400 | neither |
  | valid HMAC + unsupported `update_type` | 400 | neither |

- [ ] **Minimal auth/parse GREEN.** Compare path secret with configured secret
  by `secrets.compare_digest`; derive binary key with
  `hashlib.sha256(api_token.encode()).digest()`, calculate HMAC from
  `request.body`, compare hex digest constant-time, and only then run strict
  nested serializer. Webhook has no `BotAuthToken` permission.

  ```python
  class CryptoPayWebhookView(APIView):
      authentication_classes = ()
      permission_classes = ()
      http_method_names = ["post"]

      def post(self, request: Request, webhook_secret: str) -> Response:
          configured_secret = settings.CRYPTOPAY_WEBHOOK_SECRET
          if not configured_secret or not secrets.compare_digest(
              webhook_secret, configured_secret,
          ):
              raise Http404
          raw_body = request.body
          supplied = request.headers.get("crypto-pay-api-signature", "")
          key = hashlib.sha256(settings.CRYPTOPAY_API_TOKEN.encode()).digest()
          expected = hmac.new(key, raw_body, hashlib.sha256).hexdigest()
          if not supplied or not secrets.compare_digest(supplied, expected):
              return Response(status=status.HTTP_401_UNAUTHORIZED)
          try:
              parsed = json.loads(raw_body)
          except (UnicodeDecodeError, JSONDecodeError):
              return Response(status=status.HTTP_400_BAD_REQUEST)
          serializer = CryptoWebhookSerializer(data=parsed)
          serializer.is_valid(raise_exception=True)
          if serializer.validated_data["update_type"] != "invoice_paid":
              return Response(status=status.HTTP_400_BAD_REQUEST)
          return self._handle_signed(serializer=serializer)
  ```

- [ ] **RED semantic matrix.** Parameterize exact cases: unknown invoice,
  payload/public UUID, `currency_type`, fiat, Decimal amount, accepted-assets
  set, paid asset, provider expiration, missing/late paid_at and status mismatch.
  Unknown/mismatch returns `CryptoWebhookWarningDTO`; valid delayed invoice
  returns `ValidatedCryptoPaymentDTO`. Unsupported `update_type` is signed 400
  without alert; `invoice_paid` with non-paid status is `status_mismatch` alert.

  ```python
  def test_mismatch_returns_exact_safe_reason(self) -> None:
      cases = (
          ("status", "active", "status_mismatch"),
          ("payload", "wrong-public-id", "payload_mismatch"),
          ("currency_type", "crypto", "fiat_mismatch"),
          ("fiat", "USD", "fiat_mismatch"),
          ("amount", Decimal("98.99"), "amount_mismatch"),
          ("accepted_assets", frozenset({"USDT"}), "accepted_assets_mismatch"),
          ("paid_asset", "BTC", "paid_asset_mismatch"),
          ("expiration_date", datetime(2026, 8, 2, 12, 31, tzinfo=UTC), "expiration_mismatch"),
          ("paid_at", None, "paid_at_mismatch"),
          ("paid_at", datetime(2026, 8, 2, 12, 31, tzinfo=UTC), "paid_at_mismatch"),
      )
      for field, value, reason in cases:
          with self.subTest(field=field):
              invoice = replace(self.valid_invoice, **{field: value})
              result = self.service(update_id=42, invoice=invoice)
              self.assertEqual(result, CryptoWebhookWarningDTO(
                  reason=reason, update_id=42,
                  invoice_id=invoice.invoice_id, intent_id=self.intent.pk,
              ))
              self.assertEqual(Payment.objects.count(), 0)
  ```

- [ ] **Minimal semantic GREEN.** Check in the architecture order. Allowed
  reason strings are exactly `unknown_invoice`, `payload_mismatch`,
  `fiat_mismatch`, `amount_mismatch`, `accepted_assets_mismatch`,
  `paid_asset_mismatch`, `expiration_mismatch`, `paid_at_mismatch`, and
  `status_mismatch`. Current wall clock/local expiry never rejects a timely
  provider `paid_at`.

  ```python
  def __call__(
      self, *, update_id: int | None, invoice: CryptoInvoiceDTO
  ) -> ValidatedCryptoPaymentDTO | CryptoWebhookWarningDTO:
      intent = get_crypto_intent_by_provider_invoice_id(
          provider_invoice_id=invoice.invoice_id,
      )
      if intent is None:
          return CryptoWebhookWarningDTO(
              reason="unknown_invoice", update_id=update_id,
              invoice_id=invoice.invoice_id, intent_id=None,
          )
      checks = (
          (invoice.status == "paid", "status_mismatch"),
          (invoice.payload == str(intent.public_id), "payload_mismatch"),
          (invoice.currency_type == "fiat" and invoice.fiat == "RUB", "fiat_mismatch"),
          (invoice.amount == intent.rub_amount, "amount_mismatch"),
          (invoice.accepted_assets == frozenset({"USDT", "TON"}), "accepted_assets_mismatch"),
          (invoice.paid_asset in {"USDT", "TON"}, "paid_asset_mismatch"),
          (invoice.expiration_date == intent.provider_expires_at, "expiration_mismatch"),
          (
              invoice.paid_at is not None
              and invoice.paid_at <= intent.provider_expires_at,
              "paid_at_mismatch",
          ),
      )
      for matches, reason in checks:
          if not matches:
              return CryptoWebhookWarningDTO(
                  reason=reason, update_id=update_id,
                  invoice_id=invoice.invoice_id, intent_id=intent.pk,
              )
      return ValidatedCryptoPaymentDTO(intent_id=intent.pk, invoice=invoice)
  ```

- [ ] **RED/GREEN warning safety.** For every warning case assert one structured
  log and one `.delay()` payload containing only `reason`, `update_id`,
  `invoice_id`, optional local numeric `intent_id`. Patch core Telegram
  transport; assert warning text contains those fields and excludes test token,
  path secret, signature, raw JSON, public UUID/payload, Telegram username/ID,
  invoice URL, gift code and VPN URL. Enqueue failure→503; successful enqueue→
  200 with no fulfillment. Invalid secret/HMAC never warns.

  ```python
  SAFE_WARNING = {
      "reason": "amount_mismatch",
      "update_id": 42,
      "invoice_id": 731,
      "intent_id": 9,
  }

  @patch("apps.payments.tasks.send_telegram_message")
  def test_admin_warning_contains_only_allowlisted_fields(self, send: Mock) -> None:
      warn_crypto_webhook_admin_task.run(SAFE_WARNING)
      text = send.call_args.kwargs["text"]
      for value in SAFE_WARNING.values():
          self.assertIn(str(value), text)
      for forbidden in (
          "test-api-token", "path-secret", "signature", "raw-body",
          "1487189460", "https://t.me/CryptoBot", "KEY-ABCD-1234",
          "https://vpn.example/subscription/secret",
      ):
          self.assertNotIn(forbidden, text)

  @shared_task
  def warn_crypto_webhook_admin_task(
      warning: dict[str, int | str | None],
  ) -> None:
      safe = {key: warning.get(key) for key in (
          "reason", "update_id", "invoice_id", "intent_id",
      )}
      send_telegram_message(
          chat_id=settings.MY_TELEGRAM_ID,
          text=(
              "⚠️ <b>Crypto Pay webhook rejected</b>\n"
              f"reason={escape(str(safe['reason']))} "
              f"update_id={safe['update_id']} invoice_id={safe['invoice_id']} "
              f"intent_id={safe['intent_id']}"
          ),
          timeout=settings.TELEGRAM_TIMEOUT,
      )
  ```

- [ ] **Approved webhook HTTP semantics.** Test valid new fulfillment→200,
  matching fulfilled duplicate→200/no-op, signed unknown/mismatch→200 only after
  enqueue, malformed/unsupported→400, auth→404/401 and temporary apply/DB lock→
  503 with intent unfinished.

  ```python
  def test_signed_unknown_returns_200_only_after_warning_enqueue(self) -> None:
      event = {
          "update_id": 42,
          "update_type": "invoice_paid",
          "payload": {
              "invoice_id": 999999, "status": "paid",
              "currency_type": "fiat", "fiat": "RUB", "amount": "99.00",
              "accepted_assets": "USDT,TON", "paid_asset": "USDT",
              "payload": "0f57a4f1-1956-45be-8dc0-d891c00c74c1",
              "bot_invoice_url": "https://t.me/CryptoBot?start=test",
              "created_at": "2026-08-02T12:00:00Z",
              "expiration_date": "2026-08-02T12:30:00Z",
              "paid_at": "2026-08-02T12:20:00Z",
          },
      }
      raw = json.dumps(event, separators=(",", ":")).encode()
      response = self.client.generic(
          "POST", "/api/v1/payments/crypto/webhooks/path-secret/",
          raw, content_type="application/json",
          HTTP_CRYPTO_PAY_API_SIGNATURE=_signature(raw=raw),
      )
      self.assertEqual(response.status_code, 200)
      self.apply.assert_not_called()
      self.warn.delay.assert_called_once_with({
          "reason": "unknown_invoice", "update_id": event["update_id"],
          "invoice_id": 999999, "intent_id": None,
      })
  ```

  | Signed scenario | status | apply calls | warning enqueue |
  |---|---:|---:|---:|
  | valid new | 200 | 1 | 0 |
  | matching fulfilled duplicate | 200 | 1 (returns no-op) | 0 |
  | unknown/mismatch | 200 | 0 | 1 before response |
  | warning enqueue error | 503 | 0 | attempted once |
  | temporary apply/SQLite error | 503 | 1 | 0 |

  `_handle_signed` converts serializer data into the globally declared
  `CryptoInvoiceDTO`, calls validator with the concrete `update_id`, logs only
  the four warning fields, requires successful warning `.delay(asdict(result))`
  before returning 200, and maps `CryptoPaymentRetryable`/`OperationalError` to
  503. A `ValidatedCryptoPaymentDTO` is passed unchanged to apply.

- [ ] **Request log redaction.** Before logging, replace the webhook path with
  `/api/v1/payments/crypto/webhooks/[REDACTED]/`; for this route log only method
  and redacted path—never request headers or body. Preserve current non-webhook
  behavior and VPN redaction regression.

  ```python
  _CRYPTO_WEBHOOK_PATH = compile(r"^/api/v1/payments/crypto/webhooks/[^/]+/$")

  def _decode_body(raw_body: bytes) -> object:
      try:
          return json.loads(raw_body)
      except (JSONDecodeError, UnicodeDecodeError):
          return raw_body.decode("utf-8", errors="replace")

  def _safe_request_log(request) -> dict[str, object]:
      if _CRYPTO_WEBHOOK_PATH.fullmatch(request.path):
          return {
              "method": request.method,
              "path": "/api/v1/payments/crypto/webhooks/[REDACTED]/",
          }
      return {
          "method": request.method,
          "path": request.path,
          "headers": dict(request.headers),
          "body": _decode_body(request.body),
      }

  def test_webhook_logging_omits_secret_headers_and_body(self) -> None:
      with self.assertLogs("config.middlewares", level="INFO") as captured:
          self.client.generic(
              "POST", "/api/v1/payments/crypto/webhooks/path-secret/",
              b'{"payload":"private"}', content_type="application/json",
              HTTP_CRYPTO_PAY_API_SIGNATURE="signature",
          )
      log = "\n".join(captured.output)
      self.assertIn("[REDACTED]", log)
      self.assertNotIn("path-secret", log)
      self.assertNotIn("signature", log)
      self.assertNotIn("private", log)
  ```

- [ ] **Verify task.** Run:

  ```bash
  make test ARGS="apps.payments.tests.test_validate_crypto_invoice_service apps.payments.tests.test_views.test_crypto_webhook_view apps.payments.tests.test_crypto_admin_warning_task apps.core.tests.test_crypto_webhook_logging"
  ```

**Documentation:** stable reason-code and security docstrings only; public docs
deferred.

**Completion criterion:** raw HMAC vector, secret-path, complete semantic matrix,
delayed payment, duplicate no-op, safe warning/log allowlist and every HTTP
status pass; forbidden values are absent from both middleware logs and warnings.

**Task packet CPAY-B5:** `scope_revision: 2`; ID `CPAY-005`; allowed files are
the 13 paths above; forbidden work is fulfillment behavior, reconciliation,
create flow, models, bot/docs and alert persistence/metrics; budget ≤13 files and
≤1000 changed lines; completion requires the security matrix GREEN and separate
read-only review. Only root commits. Parallelism allowed only with CPAY-B8.

---

### CPAY-006 — Reconcile paid unfinished intents every 10 minutes

**Result:** Celery Beat fetches bounded unfinished invoice batches every ten
minutes, reuses the same semantic validator/apply service, marks provider expiry,
isolates invoice failures and re-enqueues missed user notifications.

**Traceability:** BR-006, BR-008..BR-010; AC-006, AC-008, AC-010.

**Dependencies:** CPAY-005 approved batch review.

**Files and ownership:**

- Create: `src/apps/payments/services/reconcile_crypto_payments.py`.
- Modify: `src/apps/payments/services/__init__.py`,
  `src/apps/payments/tasks.py`, `src/config/settings/celery.py`.
- Create/Test: `src/apps/payments/tests/test_reconcile_crypto_payments_service.py`,
  `test_crypto_reconciliation_task.py`, `test_crypto_reconciliation_schedule.py`.
- No models/client/webhook/bot/docs changes.

**Interfaces:** consumes CPAY-001 unfinished/unnotified selectors, CPAY-002
`get_invoices`, CPAY-005 validator and CPAY-004 apply/notification task. Produces
`ReconcileCryptoPaymentsService`, `get_reconcile_crypto_payments_service()` and
`reconcile_crypto_payments_task() -> dict[str, int]` with exact counter keys
`checked`, `paid`, `fulfilled`, `provider_expired`, `retryable_failed`,
`notifications_enqueued`.

- [ ] **RED service tests.** Add exact tests for selector status set
  `ACTIVE|LOCAL_EXPIRED|RETRYABLE`, bounded provider batches, paid→same
  validate/apply instances, active→no change, expired→conditional
  `PROVIDER_EXPIRED`, fulfilled omission, one invoice failure not stopping later
  items, common provider failure propagated, and unnotified fulfilled intents
  re-enqueued once in the run.

  ```python
  def test_paid_unfinished_uses_same_validator_and_apply(self) -> None:
      intent = CryptoPaymentIntentFactory(
          status=CryptoPaymentIntentStatusEnum.RETRYABLE,
          provider_invoice_id=731,
      )
      paid = make_crypto_invoice(invoice_id=731, status="paid")
      self.client.get_invoices.return_value = [paid]
      validated = ValidatedCryptoPaymentDTO(intent_id=intent.pk, invoice=paid)
      self.validator.return_value = validated
      self.apply.return_value = ApplyCryptoPaymentOut(
          fulfilled=True, already_fulfilled=False,
      )
      counters = self.service()
      self.validator.assert_called_once_with(update_id=None, invoice=paid)
      self.apply.assert_called_once_with(payment=validated)
      self.assertEqual(counters, {
          "checked": 1, "paid": 1, "fulfilled": 1,
          "provider_expired": 0, "retryable_failed": 0,
          "notifications_enqueued": 0,
      })
  ```

  | Provider item/result | Expected effect |
  |---|---|
  | `paid` + valid | validator then apply |
  | `active` | no state change |
  | `expired` | conditional `PROVIDER_EXPIRED` |
  | per-item validation/apply error | increment `retryable_failed`, continue |
  | request-wide `CryptoPayClientError` | escape service for Celery autoretry |
  | fulfilled + no `notification_sent_at` | enqueue once, increment counter |

- [ ] **Run RED.** From root:

  ```bash
  make test ARGS="apps.payments.tests.test_reconcile_crypto_payments_service apps.payments.tests.test_crypto_reconciliation_task apps.payments.tests.test_crypto_reconciliation_schedule"
  ```

  Expected: missing reconciliation service/task/schedule.

- [ ] **Minimal GREEN.** Use fixed code constants `GET_INVOICES_BATCH_SIZE = 100`
  and notification batch limit 100; never request rates/create invoices/change
  Product price. Validate each paid DTO with the same service using
  `update_id=None` (reconciliation is not a signed webhook and never enqueues a
  webhook admin warning), then isolate
  per-invoice validation/apply errors while logging only safe provider/local IDs
  and reason code. A request-wide client error escapes so Celery retry handles it.

  ```python
  GET_INVOICES_BATCH_SIZE = 100
  NOTIFICATION_BATCH_SIZE = 100

  def __call__(self) -> dict[str, int]:
      counters = {key: 0 for key in (
          "checked", "paid", "fulfilled", "provider_expired",
          "retryable_failed", "notifications_enqueued",
      )}
      intents = list(get_unfinished_crypto_intents(limit=GET_INVOICES_BATCH_SIZE))
      by_invoice_id = {intent.provider_invoice_id: intent for intent in intents}
      for offset in range(0, len(intents), GET_INVOICES_BATCH_SIZE):
          batch = intents[offset:offset + GET_INVOICES_BATCH_SIZE]
          invoices = self.crypto_pay_client.get_invoices(
              invoice_ids=[intent.provider_invoice_id for intent in batch],
          )
          for invoice in invoices:
              counters["checked"] += 1
              intent = by_invoice_id[invoice.invoice_id]
              try:
                  if invoice.status == "paid":
                      counters["paid"] += 1
                      validated = self.validate_invoice_service(
                          update_id=None, invoice=invoice,
                      )
                      if isinstance(validated, CryptoWebhookWarningDTO):
                          counters["retryable_failed"] += 1
                          continue
                      applied = self.apply_payment_service(payment=validated)
                      counters["fulfilled"] += int(applied.fulfilled)
                  elif invoice.status == "expired":
                      counters["provider_expired"] += mark_crypto_intent_provider_expired(
                          intent_id=intent.pk,
                      )
              except (CryptoPaymentRetryable, OperationalError):
                  counters["retryable_failed"] += 1
                  continue
      for intent in get_unnotified_fulfilled_crypto_intents(
          limit=NOTIFICATION_BATCH_SIZE,
      ):
          self.enqueue_notification(intent_id=intent.pk)
          counters["notifications_enqueued"] += 1
      return counters
  ```

- [ ] **Task/schedule.** Make reconciliation task `bind=True`,
  `autoretry_for=(CryptoPayClientError,)`, bounded backoff/retries, return and
  structured-log exact counters. Add Beat entry task
  `apps.payments.tasks.reconcile_crypto_payments_task` with
  `crontab(minute="*/10")`.

  ```python
  @shared_task(
      bind=True,
      autoretry_for=(CryptoPayClientError,),
      retry_backoff=True,
      retry_backoff_max=300,
      max_retries=3,
  )
  def reconcile_crypto_payments_task(self) -> dict[str, int]:
      counters = get_reconcile_crypto_payments_service()()
      logger.info("crypto_reconciliation_complete", extra=counters)
      return counters

  CELERY_BEAT_SCHEDULE["reconcile-crypto-payments"] = {
      "task": "apps.payments.tasks.reconcile_crypto_payments_task",
      "schedule": crontab(minute="*/10"),
  }

  def test_reconciliation_runs_every_ten_minutes(self) -> None:
      entry = settings.CELERY_BEAT_SCHEDULE["reconcile-crypto-payments"]
      self.assertEqual(entry["task"], "apps.payments.tasks.reconcile_crypto_payments_task")
      self.assertEqual(entry["schedule"]._orig_minute, "*/10")
  ```

- [ ] **Verify task.** Repeat the RED command and also run:

  ```bash
  make test ARGS="apps.payments.tests.test_reconcile_crypto_payments_service apps.payments.tests.test_crypto_reconciliation_task apps.payments.tests.test_crypto_reconciliation_schedule apps.payments.tests.test_apply_crypto_payment_service"
  ```

**Documentation:** reconciliation service/task docstrings; global schedule and
operations docs belong to CPAY-009.

**Completion criterion:** schedule is exactly 10 minutes; paid unfinished
payments use the same validator/apply path, duplicate remains no-op, provider
expiry and counters are correct, one invoice failure is isolated, global client
failure retries, and missed notifications are re-enqueued.

**Task packet CPAY-B6:** `scope_revision: 2`; ID `CPAY-006`; allowed files are
the 7 files above; forbidden work is new model/queue/outbox/metrics, create,
webhook, bot/docs and provider rates; budget ≤7 files and ≤650 changed lines;
complete on targeted GREEN and independent review before root checkpoint.

---

### CPAY-007 — Add decimal-safe Crypto invoice method to the bot client

**Result:** the bot posts initiator/kind through the existing authenticated
BackendClient and maps the exact four-field response without float conversion or
backend secrets.

**Traceability:** BR-002, BR-004, BR-007, BR-010..BR-011; AC-002, AC-011.

**Dependencies:** CPAY-003 approved batch review. May run in parallel only with
CPAY-B4.

**Files and ownership:** modify `bot/src/domains/payments/client.py`,
`bot/src/domains/payments/__init__.py`,
`bot/tests/domains/payments/test_client.py`. No handlers/keyboards/messages,
backend, config/env or docs.

**Interfaces:** produces:

```python
@dataclass(kw_only=True, slots=True, frozen=True)
class CryptoInvoice:
    invoice_url: str
    rub_amount: str
    expires_at: str
    reused: bool

async def create_crypto_invoice(
    self, *, telegram_id: str | int, purchase_kind: str
) -> CryptoInvoice:
```

Path is exactly `/api/v1/payments/crypto/invoices/`; form body contains only
`username=str(telegram_id)` and `purchase_kind`; `BackendClient` continues to
add the existing `Bot-Auth-Token`.

- [ ] **RED.** Add
  `test_create_crypto_invoice_posts_kind_and_maps_exact_decimal_string`, using
  response `{"invoice_url":"https://t.me/CryptoBot?start=x","rub_amount":"99.00","expires_at":"2026-08-02T12:30:00Z","reused":false}`.
  Assert dataclass equality, exact request fields/header and no provider token/
  secret. Run:

  ```python
  @respx.mock
  async def test_create_crypto_invoice_posts_kind_and_maps_exact_decimal_string(
      client: PaymentsClient,
  ) -> None:
      route = respx.post(f"{BASE}/api/v1/payments/crypto/invoices/").mock(
          return_value=httpx.Response(200, json={
              "invoice_url": "https://t.me/CryptoBot?start=x",
              "rub_amount": "99.00",
              "expires_at": "2026-08-02T12:30:00Z",
              "reused": False,
          }),
      )
      result = await client.create_crypto_invoice(
          telegram_id=42, purchase_kind="subscription",
      )
      assert result == CryptoInvoice(
          invoice_url="https://t.me/CryptoBot?start=x",
          rub_amount="99.00",
          expires_at="2026-08-02T12:30:00Z",
          reused=False,
      )
      assert parse_qs(route.calls.last.request.content) == {
          b"username": [b"42"], b"purchase_kind": [b"subscription"],
      }
      assert route.calls.last.request.headers["Bot-Auth-Token"] == "t"
  ```

  ```bash
  cd bot && uv run pytest tests/domains/payments/test_client.py::test_create_crypto_invoice_posts_kind_and_maps_exact_decimal_string -q
  ```

  Expected: import/attribute failure for `CryptoInvoice` or method.

- [ ] **Minimal GREEN.** Add the dataclass, method and explicit export; preserve
  `rub_amount`/`expires_at` as strings and pass `telegram_id` only to
  BackendClient error attribution and `username` form field.

  ```python
  _CRYPTO_INVOICE_PATH = "/api/v1/payments/crypto/invoices/"

  @final
  @dataclass(kw_only=True, slots=True, frozen=True)
  class CryptoInvoice:
      invoice_url: str
      rub_amount: str
      expires_at: str
      reused: bool

  async def create_crypto_invoice(
      self, *, telegram_id: str | int, purchase_kind: str
  ) -> CryptoInvoice:
      response = await self.backend.post(
          _CRYPTO_INVOICE_PATH,
          data={"username": str(telegram_id), "purchase_kind": purchase_kind},
          telegram_id=telegram_id,
      )
      return CryptoInvoice(
          invoice_url=str(response["invoice_url"]),
          rub_amount=str(response["rub_amount"]),
          expires_at=str(response["expires_at"]),
          reused=bool(response["reused"]),
      )

  __all__ = [
      "ActivatedGiftCertificate", "CryptoInvoice", "GiftCertificate",
      "PaymentsClient", "StarsInvoice",
  ]
  ```

- [ ] **Verify task.** Run:

  ```bash
  cd bot && uv run pytest tests/domains/payments/test_client.py -q
  ```

**Documentation:** docstrings only; bot README/global contracts in CPAY-009.

**Completion criterion:** exact response maps without float/datetime mutation,
request has two fields and BotAuth header, existing Stars/gift confirmation
client tests remain green, and no Crypto secret/config exists in bot.

**Task packet CPAY-B7:** `scope_revision: 2`; ID `CPAY-007`; allowed files are
exactly the 3 listed; forbidden work is handlers/UI/config/backend/docs and
changes to Stars methods; budget ≤3 files and ≤220 changed lines; complete on
full payment-client GREEN and independent review. Root alone commits. Parallel
only with CPAY-B4.

---

### CPAY-008 — Show Crypto second and handle all three bot callbacks

**Result:** MTProto, VPN and gift screens retain Stars first and add Crypto
second; each callback requests the correct kind and shows a CryptoBot URL +
expiry, while backend/provider failures remain safely retryable by another tap.

**Traceability:** BR-001, BR-004, BR-010..BR-011; AC-001..AC-002, AC-009,
AC-011.

**Dependencies:** CPAY-007 approved batch review. May run in parallel only with
CPAY-B5.

**Files and ownership:** modify `bot/src/keyboards.py`, `messages.py`,
`handlers/payments.py`, `handlers/vpn.py`, `bot/tests/test_handlers.py`. No bot
client/backend/config/docs.

**Interfaces:** consumes `PaymentsClient.create_crypto_invoice`; produces
callbacks `pay_crypto`→`subscription`, `vpn_pay_crypto`→`vpn_subscription`,
`gift_crypto`→`gift_certificate`. The success markup is one URL button using the
returned `invoice_url` plus the existing appropriate back button; handler copy
shows returned `rub_amount` and `expires_at` and does not poll payment.

- [ ] **RED keyboard regression matrix.** Update exact tests so each payment
  keyboard rows are Stars, Crypto, Back in that order, with callback strings
  above. Preserve existing Stars button text, style, callback and invoice
  payload assertions unchanged. Run:

  ```python
  @pytest.mark.parametrize(
      ("markup", "expected_callbacks"),
      [
          (keyboards.payment_methods(), ["pay_stars", "pay_crypto", "show_mtproxy_menu"]),
          (keyboards.vpn_payment_methods(stars_price=149), ["vpn_pay_stars", "vpn_pay_crypto", "show_vpn_menu"]),
          (keyboards.gift_certificate_payment_methods(), ["gift_stars", "gift_crypto", "show_mtproxy_menu"]),
      ],
  )
  def test_stars_first_crypto_second(markup, expected_callbacks) -> None:
      assert [row[0].callback_data for row in markup.inline_keyboard] == expected_callbacks
      assert markup.inline_keyboard[0][0].text.startswith("⭐ Telegram Stars")
      assert markup.inline_keyboard[1][0].text == "💎 Crypto Pay"
  ```

  ```bash
  cd bot && uv run pytest tests/test_handlers.py -k "payment_screen or gift_certificate_screen or vpn_purchase_fetches" -q
  ```

  Expected: exact row assertions fail because Crypto rows are absent.

- [ ] **Minimal keyboard/copy GREEN.** Add only one Crypto row to each builder
  and approved common text explaining Crypto invoice/error/retry. Do not alter
  Stars rows, pre-checkout or successful-payment code.

  ```python
  CRYPTO_PAY_BUTTON = "💎 Crypto Pay"
  CRYPTO_INVOICE_TEXT = (
      "💎 <b>Счёт Crypto Pay</b>\n\n"
      "Сумма: <b>{rub_amount} RUB</b>\n"
      "Действует до: <b>{expires_at}</b>\n\n"
      "Нажмите кнопку ниже, чтобы открыть CryptoBot."
  )
  CRYPTO_INVOICE_ERROR_TEXT = (
      "Не удалось создать счёт Crypto Pay. Попробуйте нажать кнопку ещё раз."
  )

  def payment_methods() -> InlineKeyboardMarkup:
      return InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(
              text="⭐ Telegram Stars — 99 ★",
              callback_data="pay_stars", style="primary",
          )],
          [InlineKeyboardButton(text=CRYPTO_PAY_BUTTON, callback_data="pay_crypto")],
          [_MTPROXY_BACK],
      ])
  ```

  Apply the identical second-row shape to VPN with
  `callback_data="vpn_pay_crypto"` and gift with
  `callback_data="gift_crypto"`; keep their existing first/back rows exactly.

- [ ] **RED callback matrix.** Extend `FakePayments` with recorded
  `crypto_calls`; parameterize three handlers. For a fixed `CryptoInvoice`,
  assert callback answered, exact `(telegram_id, purchase_kind)` call, displayed
  `99.00`/expiry and URL button. Add one `APIError` case asserting safe user
  message and no removal/disable of Crypto button, and a test that no polling or
  `send_invoice` occurs.

  ```python
  @pytest.mark.parametrize(
      ("handler", "purchase_kind"),
      [
          (process_pay_crypto, "subscription"),
          (process_vpn_pay_crypto, "vpn_subscription"),
          (process_gift_crypto, "gift_certificate"),
      ],
  )
  async def test_crypto_callback_uses_kind_and_shows_url(
      handler, purchase_kind: str,
  ) -> None:
      payments = FakePayments(crypto=CryptoInvoice(
          invoice_url="https://t.me/CryptoBot?start=x",
          rub_amount="99.00", expires_at="2026-08-02T12:30:00Z", reused=False,
      ))
      callback = FakeCallback(user_id=42)
      await handler(callback, make_deps(payments=payments))
      assert payments.crypto_calls == [(42, purchase_kind)]
      text, markup = callback.message.edits[0]
      assert "99.00" in text and "2026-08-02T12:30:00Z" in text
      assert markup.inline_keyboard[0][0].url == "https://t.me/CryptoBot?start=x"

  async def test_crypto_error_keeps_current_keyboard_retryable() -> None:
      payments = FakePayments(crypto_error=APIError(42, message="safe"))
      callback = FakeCallback(user_id=42)
      await process_pay_crypto(callback, make_deps(payments=payments))
      assert callback.message.edits == []
      assert callback.message.answers == [(CRYPTO_INVOICE_ERROR_TEXT, None)]
  ```

- [ ] **Minimal callback GREEN.** Each handler calls the common client method
  once and edits/answers only its current screen with returned URL/expiry. Reuse
  current global error handling semantics for 409/502/503/backend errors; do not
  add bot Crypto token, webhook handler or successful-payment route.

  ```python
  async def show_crypto_invoice(
      *, callback: CallbackQuery, deps: Dependencies, purchase_kind: str,
      back_callback: str,
  ) -> None:
      await callback.answer()
      try:
          invoice = await deps.payments.create_crypto_invoice(
              telegram_id=callback.from_user.id,
              purchase_kind=purchase_kind,
          )
      except APIError:
          await callback.message.answer(CRYPTO_INVOICE_ERROR_TEXT)
          return
      markup = InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(text="Открыть CryptoBot", url=invoice.invoice_url)],
          [InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)],
      ])
      await callback.message.edit_text(
          CRYPTO_INVOICE_TEXT.format(
              rub_amount=invoice.rub_amount,
              expires_at=invoice.expires_at,
          ),
          reply_markup=markup,
      )

  @router.callback_query(F.data == "pay_crypto")
  async def process_pay_crypto(callback: CallbackQuery, deps: Dependencies) -> None:
      await show_crypto_invoice(
          callback=callback, deps=deps, purchase_kind="subscription",
          back_callback="show_mtproxy_menu",
      )

  @router.callback_query(F.data == "gift_crypto")
  async def process_gift_crypto(callback: CallbackQuery, deps: Dependencies) -> None:
      await show_crypto_invoice(
          callback=callback, deps=deps, purchase_kind="gift_certificate",
          back_callback="show_mtproxy_menu",
      )

  # handlers/vpn.py imports show_crypto_invoice from handlers.payments
  @router.callback_query(F.data == "vpn_pay_crypto")
  async def process_vpn_pay_crypto(
      callback: CallbackQuery, deps: Dependencies,
  ) -> None:
      await show_crypto_invoice(
          callback=callback, deps=deps, purchase_kind="vpn_subscription",
          back_callback="show_vpn_menu",
      )
  ```

  No Crypto handler calls `bot.send_invoice`, schedules polling or touches
  `process_successful_payment`.

- [ ] **Verify task and Stars regressions.** Run:

  ```bash
  cd bot && uv run pytest tests/test_handlers.py tests/domains/payments/test_client.py -q
  ```

**Documentation:** user-facing copy in `messages.py`; durable docs in CPAY-009.

**Completion criterion:** three exact keyboard order tests and three callback
cases pass; success shows provider URL/expiry, failure permits another tap,
Stars payload/callback/successful-payment tests are unchanged and green, and bot
contains no polling/webhook/secrets.

**Task packet CPAY-B8:** `scope_revision: 2`; ID `CPAY-008`; allowed files are
exactly the 5 listed; forbidden work is client/backend/config/docs, Stars
semantics and bot polling/webhook; budget ≤5 files and ≤500 changed lines;
complete on bot client+handler suite GREEN and independent review. Root alone
commits. Parallel only with CPAY-B5.

---

### CPAY-009 — Synchronize docs/deploy examples and pass integration/release gates

**Result:** repository documentation/config examples describe the implemented
revision 2 contract and safe rollout/rollback, every required backend/bot/static/
migration/Compose check is green, a non-production testnet smoke is ready or
executed without payment, and root publishes an open PR for final review.

**Traceability:** BR-001..BR-012; AC-001..AC-012. Technical assignment:
documentation and release gates in workflow sections 3–5; no merge/deploy.

**Dependencies:** CPAY-001..CPAY-008 all targeted GREEN and approved batch
reviews; no file-writing agent active.

**Files and ownership:**

- Modify: `.env.example`, `docs/BUSINESS.md`, `docs/ARCHITECTURE.md`,
  `docs/CONTRACTS.md`, `docs/MODELS.md`, `docs/apps/PAYMENTS.md`,
  `docs/DEPLOY.md`, `bot/README.md`.
- Create/Test: `src/apps/core/tests/test_crypto_pay_deploy_artifacts.py` — locks
  backend-only example keys, Compose env propagation and unchanged bot config.
- Do not edit approved feature `business.md`/`architecture.md`; this `plan.md`
  is updated only by planner/root review, not implementer.
- Excluded from implementer ownership:
  `docs/features/cryptopay-all-products/acceptance.md`; product-reviewer alone
  creates it after integration, and root includes it in the final scoped files.

**Interfaces/doc responsibilities:** `.env.example` names
`CRYPTOPAY_API_TOKEN`, `CRYPTOPAY_BASE_URL=https://pay.crypt.bot`,
`CRYPTOPAY_WEBHOOK_SECRET`, `CRYPTOPAY_REQUEST_TIMEOUT=5`; none appear in bot
config/examples. Contracts document both exact endpoints/statuses/four-field
response/HMAC; models document lifecycle/constraints; architecture documents
exact-once/reconciliation; deploy documents testnet/mainnet webhook setup,
expand-only rollback and separate authorization gate.

- [ ] **RED documentation/config assertion.** Add
  `TestCryptoPayDeployArtifacts.test_backend_example_contains_crypto_settings_and_bot_has_none`
  and `test_compose_passes_backend_env_to_django_worker_and_beat`; run:

  ```bash
  make test ARGS="apps.core.tests.test_crypto_pay_deploy_artifacts"
  ```

  Expected: `.env.example` lacks the four keys. Do not assert or add literal
  secret values.

  ```python
  class TestCryptoPayDeployArtifacts(SimpleTestCase):
      def test_backend_example_contains_crypto_settings_and_bot_has_none(self) -> None:
          root = Path(__file__).resolve().parents[4]
          backend_env = (root / ".env.example").read_text(encoding="utf-8")
          bot_config = (root / "bot/src/config.py").read_text(encoding="utf-8")
          for name in (
              "CRYPTOPAY_API_TOKEN", "CRYPTOPAY_BASE_URL",
              "CRYPTOPAY_WEBHOOK_SECRET", "CRYPTOPAY_REQUEST_TIMEOUT",
          ):
              self.assertIn(f"{name}=", backend_env)
              self.assertNotIn(name, bot_config)

      def test_compose_passes_backend_env_to_django_worker_and_beat(self) -> None:
          root = Path(__file__).resolve().parents[4]
          compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
          for service in ("django", "celery-worker", "celery-beat"):
              service_block = compose.split(f"  {service}:\n", 1)[1].split("\n  ", 1)[0]
              self.assertIn("env_file:\n      - .env", service_block)
          bot_block = compose.split("  bot:\n", 1)[1].split("\n\n", 1)[0]
          self.assertNotIn("CRYPTOPAY_", bot_block)
  ```

- [ ] **Minimal config/docs GREEN.** Add example variable names/default public
  base URL only. Update the seven docs with implemented behavior and exact
  rollout order: migration/backend+worker+beat → provider webhook → bot buttons;
  rollback disables provider webhook and bot buttons but does not reverse real
  payment rows/products. Preserve Stars text and all non-goals.

  ```dotenv
  # Crypto Pay — backend Django/Celery only
  CRYPTOPAY_API_TOKEN=
  CRYPTOPAY_BASE_URL=https://pay.crypt.bot
  CRYPTOPAY_WEBHOOK_SECRET=
  CRYPTOPAY_REQUEST_TIMEOUT=5
  ```

  Documentation must copy these concrete contracts from implementation:
  `POST /api/v1/payments/crypto/invoices/` with its four-field 200 response;
  `POST /api/v1/payments/crypto/webhooks/<secret>/` with 404/401/400/200/503
  semantics; all eight intent statuses and two partial constraints; Beat
  `*/10`; rollout/expand-only rollback order above. It must state that testnet
  changes only `CRYPTOPAY_BASE_URL` and that no real payment is part of smoke.

- [ ] **Targeted backend suites.** Run from root:

  ```bash
  make test ARGS="apps.payments.tests apps.notifications.tests apps.vpn.tests apps.core.tests.test_crypto_pay_deploy_artifacts apps.core.tests.test_crypto_webhook_logging"
  ```

  Expected: PASS.

- [ ] **Mandatory bot suite.** Run:

  ```bash
  cd bot && uv run pytest -q
  ```

  Expected: all tests pass, including unchanged Stars cases.

- [ ] **Mandatory full backend suite and Django checks.** Run:

  ```bash
  make test
  (
    cd src
    python manage.py check --settings=config.test_settings
    python manage.py makemigrations --check --dry-run --settings=config.test_settings
  )
  python -m compileall -q src bot/src
  ```

  Expected: full suite PASS, system check no issues, `No changes detected`,
  compile command exits 0.

- [ ] **Compose/static/import checks available in repo.** Run:

  ```bash
  docker compose -f docker-compose.yml config --quiet
  (
    cd src
    python manage.py shell --settings=config.test_settings -c "from apps.payments.clients import CryptoPayClient; from apps.payments.services import CreateOrReuseCryptoInvoiceService, ApplyCryptoPaymentService, ValidateCryptoInvoiceService, ReconcileCryptoPaymentsService; from apps.payments.tasks import notify_crypto_purchase_task, warn_crypto_webhook_admin_task, reconcile_crypto_payments_task"
  )
  ```

  Expected: both exit 0 with no import cycle or Compose interpolation error.

- [ ] **Exact diff, ownership and secret scan.** From root, inspect every file
  and added line:

  ```bash
  git status --short
  git diff --check
  git diff --stat
  git diff --name-only
  set -o pipefail
  cryptopay_added_lines="$(mktemp)"
  trap 'rm -f "$cryptopay_added_lines"' EXIT
  git diff --unified=0 --no-ext-diff | sed -n 's/^+//p' >"$cryptopay_added_lines"
  if rg -n '([0-9]{6,}:AA[A-Za-z0-9_-]{20,}|sk_(live|test)_[A-Za-z0-9]{16,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)' "$cryptopay_added_lines"; then
    echo "secret-like value found in added lines" >&2
    exit 1
  fi
  ```

  Expected: `git diff --check` exits 0; changed paths are only the union of
  approved packets, this plan and product-reviewer-owned `acceptance.md`; the
  wrapped secret scan exits 0 only when no match is found.

- [ ] **Non-production testnet smoke readiness; never pay.** With dedicated
  Crypto Pay testnet token/secret supplied outside Git, create a local smoke env
  using `CRYPTOPAY_BASE_URL=https://testnet-pay.crypt.bot`, an existing local
  test user and active test products. Start the local stack, then create exactly
  one invoice:

  ```bash
  docker compose -f docker-compose.local.yml up -d
  curl --fail --silent --show-error \
    -H "Bot-Auth-Token: ${CRYPTOPAY_SMOKE_BOT_AUTH_TOKEN}" \
    -X POST http://127.0.0.1:8000/api/v1/payments/crypto/invoices/ \
    --data-urlencode "username=${CRYPTOPAY_SMOKE_TELEGRAM_ID}" \
    --data-urlencode "purchase_kind=subscription"
  ```

  Record only status, `rub_amount`, `expires_at`, `reused` and that an HTTPS
  invoice URL was returned; do not print/store token/secret/full URL and do not
  pay the invoice. Repeat once to confirm `reused=true`. If credentials are not
  available, record this exact smoke as `ready, not executed — testnet
  credentials required`; absence of production payment is mandatory and is not
  replaced by a production smoke.

- [ ] **Product acceptance and root integration gate.** Root compares final
  behavior to every BR/AC/non-goal, runs `product-reviewer`, fixes only confirmed
  `blocking_in_scope` through the owning original implementer and reruns affected
  batch review plus full gates. `scope_change_request`/`follow_up` do not enter
  current fix batches.

  Product-reviewer records the exact BR/AC evidence, commands and verdict in
  `docs/features/cryptopay-all-products/acceptance.md`. Root verifies that this
  is the only file product-reviewer created/changed and includes it in final
  diff, commit and PR scope; CPAY-009 implementer never edits it.

- [ ] **Root-only publication gate.** After all checks, root stages only scoped
  files, creates/pushes feature commits on `codex/cryptopay-all-products`, opens
  PR to `main` with revision 2, BR/AC, non-goals, checks, testnet-smoke status and
  deploy impact, captures exact `PR_HEAD_SHA`, and starts a fresh final
  `code-reviewer` on that SHA. Final reviewer publishes one structured comment;
  root requires `VERDICT: approved`, green `gh pr checks`, and unchanged head
  SHA. Leave PR open; do not merge or deploy.

  Final scoped artifacts are the union of CPAY-B1..B9 allowed files,
  `docs/features/cryptopay-all-products/plan.md`, the unchanged approved
  `business.md`/`architecture.md`, and product-reviewer-owned `acceptance.md`.

**Completion criterion:** docs/config examples exactly match implementation,
targeted/full/backend/bot/Django/migration/import/Compose/diff/secret checks pass,
testnet invoice smoke is safely recorded as executed-without-payment or ready
pending testnet credentials, product acceptance passes, and an open PR has a
verified unchanged head SHA plus final `VERDICT: approved`.

**Task packet CPAY-B9:** `scope_revision: 2`; ID `CPAY-009`; allowed files are
the 8 documents/examples plus optional single deploy-artifact test; forbidden
work is production logic, migrations, bot behavior, approved feature specs,
merge and deploy; budget ≤9 files and ≤500 changed lines; root owns full-suite,
integration, commits/push/PR/final review. Implementer completion is docs/config
GREEN; feature completion additionally requires every root gate above.

---

## BR/AC Traceability Matrix

| Requirement | Concrete tasks |
|---|---|
| BR-001 / AC-001 | CPAY-008 keyboard order + Stars regressions; CPAY-009 docs/full bot suite |
| BR-002 / AC-003 | CPAY-002 exact provider DTO/client; CPAY-003 price mapping; CPAY-007 decimal-safe bot DTO |
| BR-003 / AC-003 | CPAY-002 exact `USDT,TON`; CPAY-005 paid/accepted asset validation |
| BR-004 / AC-002 / AC-004 | CPAY-001 constraint/selectors; CPAY-003 lease/reuse/concurrency; CPAY-007/008 callback contract |
| BR-005 / AC-005 | CPAY-001 initiator ownership; CPAY-004 owner-based three-kind apply/result |
| BR-006 / AC-005 / AC-006 | CPAY-001 constraints; CPAY-004 exact-once/delayed apply; CPAY-005 duplicate webhook; CPAY-006 recovery |
| BR-007 / AC-002 / AC-003 / AC-007 | CPAY-002 provider boundary; CPAY-003 BotAuth endpoint; CPAY-005 secret/HMAC/semantic validation |
| BR-008 / AC-005 | CPAY-004 durable user-result task; CPAY-006 missed-notification recovery |
| BR-009 / AC-008 | CPAY-006 10-minute reconciliation using same validator/apply |
| BR-010 / AC-006..AC-009 | CPAY-003 retryable create; CPAY-004 rollback/retry; CPAY-005 safe no-op/error statuses; CPAY-006 recovery; CPAY-008 retry UI |
| BR-011 / AC-011 | CPAY-003 exact API output/reused flag; CPAY-007 exact-string mapping; CPAY-008 display |
| BR-012 / AC-012 | CPAY-005 allowlisted structured log/admin warning and forbidden-value tests |
| AC-010 | CPAY-001 additive migration; CPAY-002 backend settings/testnet URL; CPAY-006 schedule; CPAY-009 config/deploy/rollback gates |

Every BR-001..BR-012 and AC-001..AC-012 has at least one RED→GREEN production
task and an integration/documentation verification. No requirement is covered
only by prose.

## Planner Self-Review Record

- Spec coverage: BR-001..BR-012 and AC-001..AC-012 all map in the matrix and in
  individual task traceability; all business non-goals are repeated in Global
  Constraints/task packets.
- Placeholder scan: implementation actions name concrete tests, signatures,
  values, files, expected RED causes and commands; no deferred implementation or
  unnamed error handling remains.
- Type consistency: provider `expiration_date`→intent `provider_expires_at`→API
  `expires_at`; `rub_amount` remains `Decimal` in backend and `str` in bot;
  invoice IDs are `int` at provider/intent and `str` only for `Payment.charge_id`.
- Ownership/parallelism: only B4/B7 and B5/B8 are parallel; each pair has no
  dependency or file overlap. Writers of `services/__init__.py`, Crypto API
  files and `tasks.py` remain sequential.
- Right-sizing: nine independently rejectable/reviewable deliverables; no batch
  exceeds one task ID; setup/docs are folded into their consumer or integration
  task.
- Release boundary: implementers never commit; root owns checkpoints/full suite/
  PR; merge and production deploy are absent and separately authorized.
- Final planner check: `git diff --check` must pass and this planning task may
  change only `docs/features/cryptopay-all-products/plan.md`.
