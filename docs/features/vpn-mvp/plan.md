# VPN MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

- **Status:** ready_for_architecture_review
- **Scope revision:** 1

**Goal:** Добавить в существующий Telegram-бот самостоятельную 30-дневную
VPN-подписку с VLESS+REALITY и Hysteria 2 на нескольких VPN-нодах и новый
минимальный stateless node-agent.

**Architecture:** Django остаётся единственным постоянным источником истины и
формирует HAPP subscription. Центральный backend после оплаты асинхронно
вызывает идемпотентный FastAPI agent; agent держит профили только в памяти,
управляет Xray runtime API и обслуживает локальную Hysteria HTTP auth.

**Tech Stack:** Python 3.13, Django 6, DRF, Celery, SQLite, aiogram 3, FastAPI,
pytest/unittest, `responses`/`respx`, Docker Compose, Xray, Hysteria 2.

## Global Constraints

- Scope Contract: только `scope_revision: 1`, BR-001..BR-019 и AC-001..AC-011.
- Реализация production-кода только через TDD: RED → GREEN → REFACTOR.
- Сервисы backend — `@final` frozen dataclass с `kw_only=True, slots=True,
  frozen=True`; зависимости передаются через поля и module-level factories.
- ORM живёт в `selectors.py`; DTO, enum и domain exceptions — в профильных
  модулях; public symbols явно реэкспортируются из `__init__.py`.
- Новый node-agent не имеет SQLite, Redis, Celery, reconcile, delivery ledger,
  state machine, readiness, recovery worker, leases или self-healing.
- Редкие расхождения исправляются ручным повтором provisioning/backfill.
- Не изменять `apps/music/` и бизнес-правила MTProto.
- Не читать и не переиспользовать `my-vless-vds-instance`.
- Один `plan-implementer` получает не более двух пунктов плана.
- Каждый batch проверяет отдельный read-only `code-reviewer`; implementer
  получает только подтверждённые `blocking_in_scope`.
- Merge и production deploy каждого репозитория требуют отдельных явных
  разрешений пользователя.

## Repository Map

### Repository A — `my-mtproto-backend`

- `src/apps/payments/`: стабильный code товара, VPN payment kind и idempotency.
- `src/apps/vpn/`: модели, selectors, DTO, сервисы, API, tasks и admin.
- `src/apps/notifications/`: три VPN-шаблона и вызов существующего транспорта.
- `bot/src/domains/vpn/`: backend client и DTO VPN-меню.
- `bot/src/handlers/vpn.py`: меню, invoices и routing успешной оплаты.
- `docs/`: глобальные product/architecture/contract/model документы.

### Repository B — новый `my-vpn-vds-instance`

- `src/api/`: management, bootstrap/health и локальная Hysteria auth API.
- `src/domain/`: immutable profile DTO и in-memory store.
- `src/xray/`: узкий adapter Xray HandlerService.
- `src/backend/`: bootstrap client центрального Django.
- `deploy/`, Dockerfile и Compose: воспроизводимый node rollout с secret files.

## Dependency and Batch Graph

```text
P1 -> P2 -> P3 -> P4 -> P5 -> P6 -> P7
                   |
                   +----> A1 -> A2 -> A3

Integration gate: P1..P7 + A1..A3
```

- **Batch C1:** P1–P2, один implementer, только payments + базовый `apps.vpn`.
- **Batch C2:** P3–P4, один implementer, purchase + subscription API.
- **Batch C3:** P5–P6, один implementer, delivery/lifecycle/notifications.
- **Batch C4:** P7, один implementer, только `bot/` и итоговые central docs.
- **Batch N1:** A1–A2, один implementer, только новый agent repo; начинается
  после фиксации contract из P5.
- **Batch N2:** A3, отдельный implementer, только runtime/deploy agent repo.

Batch C4 и N1 могут выполняться параллельно: репозитории и файлы не пересекаются.

---

### P1: Явная идентичность товаров и VPN-платежа

**Requirements:** BR-002..BR-004; AC-001..AC-002; MTProto non-regression.

**Files:**

- Modify: `src/apps/payments/enums.py`
- Modify: `src/apps/payments/models.py`
- Modify: `src/apps/payments/selectors.py`
- Modify: `src/apps/payments/admin.py`
- Create: `src/apps/payments/migrations/0006_product_code_vpn_payment.py`
- Modify: `src/apps/payments/api/v1/views/get_product_view.py`
- Modify: `src/apps/payments/api/v1/urls.py`
- Modify: `src/apps/payments/tests/factories.py`
- Create/Test: `src/apps/payments/tests/test_models.py`
- Modify/Test: `src/apps/payments/tests/test_selectors.py`
- Modify/Test: `src/apps/payments/tests/test_views/test_get_product_view.py`
- Create/Test: `src/apps/payments/tests/test_migrations.py`

**Produces:**

```python
class ProductCodeEnum(enum.StrEnum):
    MTPROTO_30D = "mtproto_30d"
    VPN_30D = "vpn_30d"

class PaymentKindEnum(enum.StrEnum):
    SUBSCRIPTION = "subscription"
    VPN_SUBSCRIPTION = "vpn_subscription"
    GIFT_CERTIFICATE = "gift_certificate"

def get_active_product_by_code(*, code: str) -> Product | None: ...
```

- `Product.code` — unique `CharField`; data migration присваивает существующему
  продукту `mtproto_30d` и создаёт `VPN_30D` с `is_active=False`,
  `price=14900` копеек, `stars_price=149` и корректным receipt provider data.
- UniqueConstraint `(provider, charge_id, kind)` применяется к VPN kind.
- `GET /api/v1/payments/products/<code>/` отдаёт выбранный active product.
- Старый `GET /api/v1/payments/` остаётся alias для `mtproto_30d`.

- [ ] Написать model/migration/API tests для code, обеих цен, legacy alias и
  conditional VPN payment uniqueness.
- [ ] Запустить `make test ARGS="apps.payments.tests"`; убедиться в RED из-за
  отсутствующих enum/model/route.
- [ ] Добавить минимальные enum, migration, selector, admin и product route.
- [ ] Повторить `make test ARGS="apps.payments.tests"`; получить GREEN.
- [ ] Проверить обратную миграцию в migration test и выполнить refactor только
  на зелёных тестах.
- [ ] Commit: `feat: add explicit VPN product identity`.

### P2: VPN domain models и чистый генератор профилей

**Requirements:** BR-005, BR-007..BR-009, BR-018..BR-019; AC-003..AC-005.

**Files:**

- Create: `src/apps/vpn/__init__.py`
- Create: `src/apps/vpn/apps.py`
- Create: `src/apps/vpn/models.py`
- Create: `src/apps/vpn/selectors.py`
- Create: `src/apps/vpn/exceptions.py`
- Create: `src/apps/vpn/services/__init__.py`
- Create: `src/apps/vpn/services/dtos/__init__.py`
- Create: `src/apps/vpn/services/dtos/subscription_dtos.py`
- Create: `src/apps/vpn/services/build_subscription_service.py`
- Create: `src/apps/vpn/admin.py`
- Create: `src/apps/vpn/migrations/0001_initial.py`
- Modify: `src/config/settings/base.py`
- Create/Test: `src/apps/vpn/tests/factories.py`
- Create/Test: `src/apps/vpn/tests/test_models.py`
- Create/Test: `src/apps/vpn/tests/test_selectors.py`
- Create/Test: `src/apps/vpn/tests/test_build_subscription_service.py`

**Produces:**

```python
class VPNSubscription(BaseDjangoModel):
    user: OneToOneField[SystemUser]
    token: str
    vless_uuid: UUID
    hysteria_secret: str
    expired_at: datetime

class VPNInstance(BaseDjangoModel):
    number: int
    name: str
    location: str
    management_url: str
    public_host: str
    vless_port: int
    reality_sni: str
    reality_public_key: str
    reality_short_id: str
    hysteria_port: int
    hysteria_sni: str
    hysteria_obfs: str

class BuildSubscriptionService:
    def __call__(
        self, *, subscription: VPNSubscription,
        instances: Iterable[VPNInstance]
    ) -> str: ...  # Base64 newline-separated URI
```

- [ ] Написать tests на unique one-subscription/user, стабильные credentials,
  active selectors, сортировку нод, percent encoding и ровно `2 × N` URI.
- [ ] Запустить `make test ARGS="apps.vpn.tests"`; подтвердить RED.
- [ ] Добавить app, models/migration, selectors, DTO и pure generator без HTTP
  или ORM внутри `BuildSubscriptionService`.
- [ ] Повторить targeted tests до GREEN.
- [ ] Запустить migration consistency:
  `cd src && python manage.py makemigrations --check --dry-run`.
- [ ] Commit: `feat: add VPN subscription domain`.

### P3: Идемпотентная покупка и продление VPN

**Requirements:** BR-002..BR-006, BR-008, BR-012..BR-013; AC-001, AC-003,
AC-005, AC-007.

**Depends on:** P1, P2.

**Files:**

- Create: `src/apps/vpn/services/fulfill_vpn_purchase_service.py`
- Create: `src/apps/vpn/services/dtos/payment_dtos.py`
- Modify: `src/apps/vpn/services/__init__.py`
- Create: `src/apps/vpn/api/__init__.py`
- Create: `src/apps/vpn/api/urls.py`
- Create: `src/apps/vpn/api/v1/__init__.py`
- Create: `src/apps/vpn/api/v1/urls.py`
- Create: `src/apps/vpn/api/v1/serializers/__init__.py`
- Create: `src/apps/vpn/api/v1/serializers/payment_serializers.py`
- Create: `src/apps/vpn/api/v1/views/__init__.py`
- Create: `src/apps/vpn/api/v1/views/payment_views.py`
- Modify: `src/config/urls.py`
- Create: `src/config/settings/vpn.py`
- Modify: `src/config/settings/base.py`
- Modify: `src/config/settings/__init__.py`
- Modify: `.env.example`
- Create/Test: `src/apps/vpn/tests/test_fulfill_vpn_purchase_service.py`
- Create/Test: `src/apps/vpn/tests/test_payment_views.py`
- Modify/Test: `src/apps/payments/tests/test_create_payment_service.py`

**Produces:**

```python
@dataclass(kw_only=True, slots=True, frozen=True)
class FulfillVPNPaymentIn:
    username: str
    charge_id: str
    provider: str
    product_code: str

@dataclass(kw_only=True, slots=True, frozen=True)
class VPNPurchaseOut:
    expired_at: datetime
    subscription_url: str

class FulfillVPNPurchaseService:
    def __call__(self, *, payment: FulfillVPNPaymentIn) -> VPNPurchaseOut: ...
```

- New endpoint: `POST /api/v1/vpn/payments/buy/`, protected by
  `Bot-Auth-Token`.
- Request body точно содержит `username`, non-blank `charge_id`, `provider` и
  `product_code="vpn_30d"`; иное значение отклоняется без Payment mutation.
- Service атомарно создаёт `Payment(kind=VPN_SUBSCRIPTION)` и create/extends
  subscription. Повтор той же identity возвращает текущий result без продления.
- `VPN_SUBSCRIPTION_BASE_URL` из environment используется только для построения
  внешней стабильной URL; internal Django hostname в ответ bot не попадает.
- `transaction.on_commit()` вызывает injected scheduler; HTTP к ноде внутри
  платёжной транзакции запрещён.

- [ ] Написать RED tests на первую покупку, active +30 days, expired/inactive
  reset from accepted time, stable token/credentials, duplicate YuKassa/Stars и
  отсутствие влияния на MTPRotoKey.
- [ ] Запустить `make test ARGS="apps.vpn.tests.test_fulfill_vpn_purchase_service apps.vpn.tests.test_payment_views"`.
- [ ] Реализовать service, DTO, serializer/view/factory с DI и `on_commit`.
- [ ] Получить GREEN targeted tests, затем payments regression tests.
- [ ] Commit: `feat: fulfill VPN purchases`.

### P4: Публичная HAPP subscription API

**Requirements:** BR-005..BR-009, BR-018; AC-003..AC-006.

**Depends on:** P2, P3.

**Files:**

- Create: `src/apps/vpn/api/v1/views/subscription_views.py`
- Create: `src/apps/vpn/api/v1/views/menu_views.py`
- Create: `src/apps/vpn/api/v1/serializers/menu_serializers.py`
- Modify: `src/apps/vpn/api/v1/serializers/__init__.py`
- Modify: `src/apps/vpn/api/v1/views/__init__.py`
- Modify: `src/apps/vpn/api/v1/urls.py`
- Create: `src/apps/vpn/services/get_subscription_service.py`
- Modify: `src/apps/vpn/services/__init__.py`
- Modify: `nginx/nginx.conf`
- Create/Test: `src/apps/vpn/tests/test_subscription_view.py`
- Create/Test: `src/apps/vpn/tests/test_get_subscription_service.py`
- Create/Test: `src/apps/vpn/tests/test_menu_view.py`
- Create/Test: `src/apps/vpn/tests/test_subscription_logging.py`

**Produces:**

```text
GET /api/v1/vpn/subscriptions/<token>/
200 text/plain; Cache-Control: private, no-store
```

- Unknown token: `404`.
- Expired/inactive/no active instances: `200` with Base64 empty payload.
- Active: deterministic Base64 newline-separated `vless://` and `hysteria2://`.
- View performs no write or provisioning and requires no `Bot-Auth-Token`.
- `GET /api/v1/vpn/menu/?username=<telegram_id>` с `Bot-Auth-Token` выполняет
  только read-only lookup и возвращает exact JSON:

```json
{
  "status": "none|active|expired",
  "expired_at": "<ISO-8601 or null>",
  "subscription_url": "<absolute URL or null>"
}
```

- Для `none` оба nullable поля равны `null`; для `expired` URL остаётся
  стабильной, но публичный endpoint отдаёт пустую subscription.
- Nginx отключает access log только для subscription route, чтобы token не
  попадал в access logs; остальные логи не меняются.

- [ ] Написать RED API tests на menu/subscription states, headers, `2 × N`
  decode и отсутствие token/credentials в app/nginx access logs.
- [ ] Запустить targeted `make test ARGS="apps.vpn.tests.test_subscription_view apps.vpn.tests.test_get_subscription_service apps.vpn.tests.test_menu_view apps.vpn.tests.test_subscription_logging"`; подтвердить RED.
- [ ] Реализовать selector/service/views и точечное правило Nginx без
  глобального рефакторинга middleware или access logging.
- [ ] Получить GREEN и commit `feat: serve VPN subscriptions`.

### P5: Node contract, provisioning tasks и повторяемый backfill

**Requirements:** BR-010..BR-012, BR-015..BR-017, BR-019; AC-006..AC-007,
AC-009..AC-010.

**Depends on:** P2, P3. **Unblocks:** A1.

**Files:**

- Create: `src/apps/vpn/services/node_client_service.py`
- Create: `src/apps/vpn/services/schedule_profiles_service.py`
- Create: `src/apps/vpn/tasks.py`
- Create: `src/apps/vpn/api/v1/views/agent_bootstrap_views.py`
- Create: `src/apps/vpn/api/v1/serializers/agent_serializers.py`
- Modify: `src/apps/vpn/api/v1/serializers/__init__.py`
- Modify: `src/apps/vpn/api/v1/views/__init__.py`
- Modify: `src/apps/vpn/api/v1/urls.py`
- Modify: `src/apps/vpn/admin.py`
- Modify: `src/apps/vpn/selectors.py`
- Modify: `src/apps/vpn/services/__init__.py`
- Modify: `src/config/settings/vpn.py`
- Create/Test: `src/apps/vpn/tests/test_node_client_service.py`
- Create/Test: `src/apps/vpn/tests/test_tasks.py`
- Create/Test: `src/apps/vpn/tests/test_agent_bootstrap_view.py`
- Create/Test: `src/apps/vpn/tests/test_admin.py`

**Produces central-to-agent contract:**

```text
PUT    {management_url}/api/v1/profiles/{subscription_id}
DELETE {management_url}/api/v1/profiles/{subscription_id}
GET    {management_url}/health
Authorization: Bearer <VPN_AGENT_TOKEN>
```

**Produces agent-to-central bootstrap contract:**

```text
GET /api/v1/vpn/agent/profiles/
Authorization: Bearer <VPN_AGENT_TOKEN>
[{"access_id": 1, "vless_uuid": "...", "hysteria_secret": "..."}]
```

- [ ] Написать RED `responses` tests на exact paths/headers/body, idempotent
  agent responses, timeout/5xx retry, terminal admin alert without credentials,
  4xx no retry и bootstrap only-active profiles.
- [ ] Написать RED admin test: backfill action разрешён только для выбранной
  inactive ноды и повторно ставит PUT для всех current active subscriptions.
- [ ] Запустить `make test ARGS="apps.vpn.tests.test_node_client_service apps.vpn.tests.test_tasks apps.vpn.tests.test_agent_bootstrap_view apps.vpn.tests.test_admin"`; подтвердить RED до production-кода.
- [ ] Реализовать frozen infra/service classes, settings, thin Celery tasks,
  bootstrap permission и admin action без delivery models. HTTP timeout — 5
  секунд; Celery delivery task использует `max_retries=3` и фиксированный
  `countdown=10` секунд.
- [ ] Запустить `make test ARGS="apps.vpn.tests.test_node_client_service apps.vpn.tests.test_tasks apps.vpn.tests.test_agent_bootstrap_view apps.vpn.tests.test_admin"` до GREEN.
- [ ] Commit: `feat: deliver VPN profiles to nodes`.

### P6: Expiry, уведомления и административная деактивация

**Requirements:** BR-014..BR-016; AC-006, AC-008..AC-009.

**Depends on:** P2, P5.

**Files:**

- Create: `src/apps/vpn/services/expire_vpn_subscriptions_service.py`
- Create: `src/apps/vpn/services/notify_vpn_expiry_service.py`
- Modify: `src/apps/vpn/services/__init__.py`
- Modify: `src/apps/vpn/selectors.py`
- Modify: `src/apps/vpn/tasks.py`
- Modify: `src/apps/vpn/admin.py`
- Modify: `src/config/settings/celery.py`
- Create: `src/apps/notifications/migrations/0010_seed_vpn_templates.py`
- Create/Test: `src/apps/vpn/tests/test_expiry_services.py`
- Create/Test: `src/apps/vpn/tests/test_notification_services.py`
- Modify/Test: `src/apps/vpn/tests/test_tasks.py`
- Modify/Test: `src/apps/vpn/tests/test_admin.py`

**Produces:**

```python
class ExpireVPNSubscriptionsService:
    def __call__(self, *, now: datetime) -> int: ...

class NotifyVPNExpiryService:
    def __call__(self, *, window: Literal["day", "hour", "expired"]) -> int: ...
```

- [ ] Написать RED tests на day/hour/expired selection, VPN-specific callback,
  deactivate-before-delete scheduling, repeated admin action и MTProto template
  isolation.
- [ ] Запустить `make test ARGS="apps.vpn.tests.test_expiry_services apps.vpn.tests.test_notification_services apps.vpn.tests.test_tasks apps.vpn.tests.test_admin"`; подтвердить RED.
- [ ] Реализовать selectors/services, thin tasks, beat entries и три template
  slugs; использовать существующий Telegram transport.
- [ ] Получить GREEN targeted VPN/notification tests.
- [ ] Commit: `feat: expire and notify VPN subscriptions`.

### P7: Telegram-бот — VPN menu и оба payment flow

**Requirements:** BR-001..BR-006, BR-009, BR-013..BR-014; AC-001..AC-003,
AC-005, AC-008, AC-011.

**Depends on:** P1, P3, P4.

**Files:**

- Create: `bot/src/domains/vpn/__init__.py`
- Create: `bot/src/domains/vpn/client.py`
- Create: `bot/src/handlers/vpn.py`
- Modify: `bot/src/handlers/__init__.py`
- Modify: `bot/src/domains/payments/client.py`
- Modify: `bot/src/handlers/payments.py`
- Modify: `bot/src/dependencies.py`
- Modify: `bot/src/keyboards.py`
- Modify: `bot/src/messages.py`
- Create/Test: `bot/tests/domains/vpn/test_client.py`
- Modify/Test: `bot/tests/domains/payments/test_client.py`
- Modify/Test: `bot/tests/test_handlers.py`
- Modify/Test: `bot/tests/test_dependencies.py`
- Modify: `docs/BUSINESS.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/CONTRACTS.md`
- Modify: `docs/MODELS.md`
- Create: `docs/apps/VPN.md`
- Modify: `docs/DEPLOY.md`

**Produces:**

- Main callback `vpn`; payment callbacks `vpn_pay_yukassa`, `vpn_pay_stars`;
  invoice payloads `vpn_yukassa`, `vpn_stars`.
- Backend DTO:

```python
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNMenu:
    status: Literal["none", "active", "expired"]
    expired_at: str | None
    subscription_url: str | None
```

- `VPNMenu(**response)` использует exact JSON P4; handler ветвится только по
  `status`, без отдельного неявного mapping `is_active`.

- Successful VPN payment вызывает только VPN buy endpoint и отвечает сроком,
  URL и краткими шагами импорта в HAPP.

- [ ] Написать RED async client/handler tests для no-subscription, active,
  expired, YuKassa, Stars, distinct payload routing и прежних MTProto handlers.
- [ ] Запустить `cd bot && uv run pytest`; подтвердить RED в новых VPN tests до
  изменения bot production-кода.
- [ ] Реализовать focused VPN domain/handler и минимальные изменения общей
  payment router/dependencies/keyboards/messages.
- [ ] Запустить `cd bot && uv run pytest` до GREEN.
- [ ] Обновить `docs/BUSINESS.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`,
  `docs/MODELS.md` и создать `docs/apps/VPN.md`; не менять MTProto rules.
- [ ] Commit: `feat: add VPN bot experience`.

### A1: Новый stateless FastAPI agent и management contract

**Requirements:** BR-007..BR-012, BR-019; AC-004, AC-007.

**Depends on:** P5 contract. **Repository:** новый `my-vpn-vds-instance`.

**Files (all new):**

- `.gitignore`, `.python-version`, `pyproject.toml`, `uv.lock`, `Makefile`
- `src/__init__.py`, `src/app.py`, `src/config.py`, `src/factories.py`
- `src/domain/__init__.py`, `src/domain/profiles.py`, `src/domain/store.py`
- `src/security/__init__.py`, `src/security/auth.py`, `src/security/logging.py`
- `src/api/__init__.py`, `src/api/management.py`, `src/api/health.py`
- `tests/conftest.py`, `tests/test_management_api.py`, `tests/test_store.py`,
  `tests/test_auth.py`, `tests/test_logging.py`

**Produces:**

```python
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNProfile:
    access_id: int
    vless_uuid: UUID
    hysteria_secret: str

class InMemoryProfileStore:
    def get_all(self) -> tuple[VPNProfile, ...]: ...
    def get_by_secret(self, *, secret: str) -> VPNProfile | None: ...
    def upsert(self, *, profile: VPNProfile) -> None: ...
    def delete(self, *, access_id: int) -> None: ...
```

- Management bearer auth, exact PUT/DELETE paths из P5 и `GET /health`.
- Никакой постоянной БД; secrets redacted from validation/errors/logs.

- [ ] Создать новый repository/feature branch без копирования старого agent.
- [ ] Написать RED FastAPI tests на auth, validation, idempotent PUT/DELETE,
  health и log redaction.
- [ ] Запустить `uv run pytest`; подтвердить RED из-за отсутствующих app/store
  interfaces.
- [ ] Реализовать минимальный app/store/config/factories до GREEN.
- [ ] Запустить `uv run pytest` и commit `feat: add stateless VPN node agent`.

### A2: Xray adapter, Hysteria auth и startup bootstrap

**Requirements:** BR-007..BR-012, BR-019; AC-004, AC-007, AC-010.

**Depends on:** A1, P5.

**Files:**

- Create: `src/xray/__init__.py`
- Create: `src/xray/client.py`
- Create: `src/xray/service.py`
- Create: `src/backend/__init__.py`
- Create: `src/backend/client.py`
- Create: `src/services/__init__.py`
- Create: `src/services/profile_service.py`
- Create: `src/services/bootstrap_service.py`
- Create: `src/api/hysteria_auth.py`
- Modify: `src/api/management.py`, `src/api/health.py`, `src/app.py`,
  `src/factories.py`
- Create/Test: `tests/test_xray_client.py`, `tests/test_profile_service.py`,
  `tests/test_hysteria_auth.py`, `tests/test_bootstrap.py`, `tests/test_health.py`

**Produces:**

```python
class XrayClient(Protocol):
    def upsert_user(self, *, access_id: int, uuid: UUID) -> None: ...
    def delete_user(self, *, access_id: int) -> None: ...
    def health(self) -> None: ...

class BootstrapService:
    async def __call__(self) -> None: ...
```

- PUT сначала успешно применяет Xray, затем публикует profile in-memory.
- DELETE идемпотентно удаляет Xray и in-memory access.
- Local Hysteria `POST /auth` принимает официальный auth payload и отвечает
  `{"ok": bool, "id": str}`; route не публикуется наружу.
- Startup bootstrap получает все active profiles из Django, применяет их и
  только затем делает agent healthy. Периодического reconcile нет.
- При временной недоступности Django bootstrap делает 5 попыток с фиксированной
  задержкой 5 секунд; до успеха `GET /health` возвращает unhealthy. После
  исчерпания попыток процесс остаётся unhealthy и допускает ручной restart, без
  recovery worker.

- [ ] Написать RED adapter/service/auth/bootstrap tests с fake Xray и `respx`.
- [ ] Запустить `uv run pytest`; подтвердить RED, включая bounded retry и
  unhealthy-until-bootstrap-success.
- [ ] Реализовать ровно HandlerService operations, local auth и startup hook;
  не добавлять snapshot/revision/exact-set abstractions.
- [ ] Получить GREEN `uv run pytest`.
- [ ] Commit: `feat: manage Xray and Hysteria profiles`.

### A3: Runtime Compose и воспроизводимый deploy

**Requirements:** AC-004, AC-006..AC-007, AC-010; approved architecture
sections 9–11.

**Depends on:** A2, P1..P7.

**Agent repository files:**

- Create: `Dockerfile`, `docker-compose.yml`, `docker-compose.local.yml`
- Create: `.env.example`
- Create: `xray/config.json`
- Create: `hysteria/config.yaml`
- Create: `deploy/inventory.example.ini`, `deploy/playbook.yml`
- Create: `deploy/group_vars/vpn.example.yml`
- Create: `docs/DEPLOY.md`, `docs/RUNBOOK.md`, `README.md`
- Create/Test: `tests/test_compose_contract.py`, `tests/test_config_contract.py`,
  `deploy/tests/test_deploy.py`

**Runtime constraints:**

- pinned Xray and Hysteria image digests;
- Xray gRPC and Hysteria auth only on internal network;
- public TCP/443 for VLESS+REALITY and UDP/443 for Hysteria;
- agent management TLS/network restriction and secret files;
- no credentials or test-server address committed.

- [ ] Написать RED static contract tests на images, ports, private listeners,
  read-only secrets и отсутствие embedded credentials.
- [ ] Запустить `uv run pytest tests/test_compose_contract.py tests/test_config_contract.py deploy/tests/test_deploy.py`; подтвердить RED до создания runtime/deploy файлов.
- [ ] Реализовать Compose/config/Ansible/docs с нуля; не открывать production
  listeners и не запускать deploy.
- [ ] Выполнить agent `uv run pytest` и
  `docker compose -f docker-compose.yml config --quiet`.
- [ ] Выполнить central `make test`, `cd bot && uv run pytest` и
  `docker compose -f docker-compose.yml config --quiet`.
- [ ] Commit agent `chore: add VPN node deployment`.

## Review and Release Gates

1. После каждого batch остановить все write-agents, сохранить `git status` и
   diff, затем запустить отдельного read-only `code-reviewer`.
2. Reviewer классифицирует findings как `blocking_in_scope`,
   `scope_change_request` или `follow_up`. Только подтверждённые главным агентом
   `blocking_in_scope` возвращаются исходному implementer.
3. После P1..P7 главный агент запускает полный central suite и
   `product-reviewer` по BR/AC.
4. После A1..A3 запускаются полный agent suite и отдельный product acceptance
   smoke на разрешённой test environment.
5. Главный агент после обоих треков создаёт central
   `docs/features/vpn-mvp/acceptance.md` и записывает без secrets результаты
   smoke: payment → immediate URL → async PUT → HAPP `2 × N` → оба transport →
   deactivate/expiry DELETE → repeatable backfill.
6. Каждый репозиторий получает собственные feature branch, commits, push и PR.
7. Новый `code-reviewer` проверяет точный head SHA каждого PR и публикует
   `VERDICT: approved`; checks должны быть зелёными.
8. PR остаются открытыми. Merge выполняется только после отдельного явного
   разрешения пользователя для каждого проверенного SHA.
9. После merge назвать оба release SHA и запросить новое отдельное разрешение
   непосредственно перед production deploy. Разрешение на merge не разрешает
   deploy.

## Coverage Check

| Requirement | Plan items |
|---|---|
| BR-001, AC-002, AC-011 | P1, P7 |
| BR-002..BR-004, AC-001 | P1, P3, P7 |
| BR-005..BR-009, AC-003..AC-005 | P2, P3, P4, P7 |
| BR-010..BR-012, AC-007 | P3, P5, A1, A2 |
| BR-013, AC-005 | P3, P7 |
| BR-014..BR-016, AC-006, AC-008..AC-009 | P5, P6, P7 |
| BR-017, AC-010 | P5, A2, A3 |
| BR-018..BR-019 | P2, P4, P5, A2 |
| Cross-repo runtime and release gates | A3 |

## Explicitly Deferred

Reconcile, delivery/readiness tracking, automatic repair, feature flags,
reissue, device/traffic limits, metrics, automated refunds, WebSocket transport
and availability-based sale blocking require a future Scope Contract revision.
