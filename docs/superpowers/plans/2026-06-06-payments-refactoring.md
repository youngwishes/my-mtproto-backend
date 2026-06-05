# Рефакторинг apps/payments/ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Разделить монолитный `CreatePaymentService` на три сервиса с DI, ввести DTOs, селекторы, доменные исключения и документацию.

**Architecture:** Оркестратор `CreatePaymentService` принимает `CreatePaymentIn` DTO и делегирует: `ExtendKeyService` продлевает ключ, `NotifyPaymentService` отправляет уведомление. ORM-запросы вынесены в селекторы. Зависимости инъецируются через поля frozen dataclass, фабрики собирают граф.

**Tech Stack:** Django 6, DRF, Python 3.13, factory_boy, responses, unittest.mock

**Spec:** `docs/superpowers/specs/2026-06-06-payments-refactoring-design.md`

---

### Task 1: BaseServiceDTO в apps/core/

**Files:**
- Create: `src/apps/core/dtos.py`
- Modify: `src/apps/core/__init__.py`

- [ ] **Step 1: Create `src/apps/core/dtos.py`**

```python
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(kw_only=True, frozen=True, slots=True)
class BaseServiceDTO:
    """Базовый DTO для передачи данных между слоями."""

    def asdict(self) -> dict:
        return asdict(self)
```

- [ ] **Step 2: Update `src/apps/core/__init__.py`**

```python
from .models import BaseDjangoModel, ActiveQuerySet
from .dtos import BaseServiceDTO
```

- [ ] **Step 3: Verify import works**

Run: `cd src && python -c "from apps.core import BaseServiceDTO; print(BaseServiceDTO)"`
Expected: `<class 'apps.core.dtos.BaseServiceDTO'>`

---

### Task 2: Настройка SUBSCRIPTION_PERIOD_DAYS

**Files:**
- Create: `src/config/settings/payments.py`
- Modify: `src/config/settings/__init__.py`

- [ ] **Step 1: Create `src/config/settings/payments.py`**

```python
SUBSCRIPTION_PERIOD_DAYS = 30
```

- [ ] **Step 2: Add import to `src/config/settings/__init__.py`**

Add this line at the end of the file:

```python
from .payments import *
```

- [ ] **Step 3: Verify setting is accessible**

Run: `cd src && python -c "from django.conf import settings; print(settings.SUBSCRIPTION_PERIOD_DAYS)" 2>&1 | head -5`

Для этого нужно задать `DJANGO_SETTINGS_MODULE`:

Run: `cd src && DJANGO_SETTINGS_MODULE=config.settings DJANGO_SECRET_KEY=test python -c "import django; django.setup(); from django.conf import settings; print(settings.SUBSCRIPTION_PERIOD_DAYS)"`
Expected: `30`

---

### Task 3: CreatePaymentIn DTO

**Files:**
- Create: `src/apps/payments/services/dtos/__init__.py`
- Create: `src/apps/payments/services/dtos/create_payment_dto.py`

- [ ] **Step 1: Create `src/apps/payments/services/dtos/__init__.py`**

```python
from apps.payments.services.dtos.create_payment_dto import CreatePaymentIn

__all__ = ["CreatePaymentIn"]
```

- [ ] **Step 2: Create `src/apps/payments/services/dtos/create_payment_dto.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class CreatePaymentIn(BaseServiceDTO):
    """Входные данные для создания платежа."""

    username: str
    charge_id: str
    provider: str
```

- [ ] **Step 3: Verify import**

Run: `cd src && DJANGO_SETTINGS_MODULE=config.settings DJANGO_SECRET_KEY=test python -c "import django; django.setup(); from apps.payments.services.dtos import CreatePaymentIn; dto = CreatePaymentIn(username='123', charge_id='ch_1', provider='yukassa'); print(dto.asdict())"`
Expected: `{'username': '123', 'charge_id': 'ch_1', 'provider': 'yukassa'}`

---

### Task 4: Доменные исключения

**Files:**
- Create: `src/apps/payments/exceptions.py`

- [ ] **Step 1: Create `src/apps/payments/exceptions.py`**

```python
from apps.core.service import BaseServiceError


class BadPaymentData(BaseServiceError):
    """Некорректные данные платежа"""


class ProductNotFound(BaseServiceError):
    """Продукт не найден"""
```

---

### Task 5: Селектор get_active_key

**Files:**
- Create: `src/apps/vds/selectors.py`
- Create: `src/apps/vds/tests/test_selectors.py`

- [ ] **Step 1: Write failing test — create `src/apps/vds/tests/test_selectors.py`**

```python
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.selectors import get_active_key
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestGetActiveKey(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()

    def test_returns_active_key(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
        )
        result = get_active_key(user=self.user)
        self.assertEqual(result, key)

    def test_returns_none_when_no_key(self) -> None:
        result = get_active_key(user=self.user)
        self.assertIsNone(result)

    def test_returns_none_when_key_expired(self) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() - timedelta(days=1),
            was_deleted=False,
        )
        result = get_active_key(user=self.user)
        self.assertIsNone(result)

    def test_returns_none_when_key_deleted(self) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=True,
        )
        result = get_active_key(user=self.user)
        self.assertIsNone(result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && python manage.py test apps.vds.tests.test_selectors -v2`
Expected: `ImportError` — `get_active_key` не существует.

- [ ] **Step 3: Write implementation — create `src/apps/vds/selectors.py`**

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone

from apps.vds.models import MTPRotoKey

if TYPE_CHECKING:
    from apps.users.models import SystemUser


def get_active_key(*, user: SystemUser) -> MTPRotoKey | None:
    """Активный (не удалённый, не истёкший) ключ пользователя."""
    return MTPRotoKey.objects.filter(
        user=user,
        was_deleted=False,
        expired_date__gt=timezone.now(),
    ).first()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && python manage.py test apps.vds.tests.test_selectors -v2`
Expected: 4 tests pass.

---

### Task 6: Селектор get_user_by_username

**Files:**
- Create: `src/apps/users/selectors.py`
- Create: `src/apps/users/tests/test_selectors.py`

- [ ] **Step 1: Write failing test — create `src/apps/users/tests/test_selectors.py`**

```python
from __future__ import annotations

from django.test import TestCase

from apps.users.selectors import get_user_by_username
from apps.users.tests.factories import SystemUserFactory


class TestGetUserByUsername(TestCase):
    def test_returns_user_when_exists(self) -> None:
        user = SystemUserFactory(username="123456")
        result = get_user_by_username(username="123456")
        self.assertEqual(result, user)

    def test_returns_none_when_not_found(self) -> None:
        result = get_user_by_username(username="nonexistent")
        self.assertIsNone(result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && python manage.py test apps.users.tests.test_selectors -v2`
Expected: `ImportError` — `get_user_by_username` не существует.

- [ ] **Step 3: Write implementation — create `src/apps/users/selectors.py`**

```python
from __future__ import annotations

from apps.users.models import SystemUser


def get_user_by_username(*, username: str) -> SystemUser | None:
    """Находит пользователя по Telegram ID (хранится в поле username)."""
    return SystemUser.objects.filter(username=username).first()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && python manage.py test apps.users.tests.test_selectors -v2`
Expected: 2 tests pass.

---

### Task 7: ExtendKeyService

**Files:**
- Create: `src/apps/payments/services/extend_key_service.py`
- Create: `src/apps/payments/tests/test_extend_key_service.py`

- [ ] **Step 1: Write failing test — create `src/apps/payments/tests/test_extend_key_service.py`**

```python
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from apps.payments.models import Payment
from apps.payments.services.extend_key_service import get_extend_key_service
from apps.payments.tests.factories import PaymentFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestExtendKeyService(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()
        self.service = get_extend_key_service()

    def test_extends_key_by_subscription_period(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
        )
        original_expired = key.expired_date

        self.service(key=key)

        key.refresh_from_db()
        self.assertAlmostEqual(
            key.expired_date,
            original_expired + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )

    def test_detaches_old_payments_from_key(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
        )
        old_payment = PaymentFactory(user=self.user, key=key)

        self.service(key=key)

        old_payment.refresh_from_db()
        self.assertIsNone(old_payment.key)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && python manage.py test apps.payments.tests.test_extend_key_service -v2`
Expected: `ImportError` — модуль не существует.

- [ ] **Step 3: Write implementation — create `src/apps/payments/services/extend_key_service.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, final

from django.conf import settings
from django.db import transaction

from apps.payments.models import Payment

if TYPE_CHECKING:
    from apps.vds.models import MTPRotoKey


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ExtendKeyService:
    """Продлевает активный ключ на SUBSCRIPTION_PERIOD_DAYS дней.

    Отвязывает предыдущие платежи от ключа (key=NULL),
    чтобы новый Payment стал единственным владельцем связи.
    """

    def __call__(self, *, key: MTPRotoKey) -> None:
        with transaction.atomic():
            key.expired_date += timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS)
            key.save(update_fields=["expired_date"])
            Payment.objects.filter(key=key).update(key=None)


def get_extend_key_service() -> ExtendKeyService:
    return ExtendKeyService()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && python manage.py test apps.payments.tests.test_extend_key_service -v2`
Expected: 2 tests pass.

---

### Task 8: NotifyPaymentService

**Files:**
- Create: `src/apps/payments/services/notify_payment_service.py`
- Create: `src/apps/payments/tests/test_notify_payment_service.py`

- [ ] **Step 1: Write failing test — create `src/apps/payments/tests/test_notify_payment_service.py`**

```python
from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.payments.services.notify_payment_service import get_notify_payment_service
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestNotifyPaymentService(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()
        self.service = get_notify_payment_service()

    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    def test_sends_proxy_link_to_user(self, mock_send: mock.Mock) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=30),
            was_deleted=False,
        )

        self.service(user=self.user, key=key)

        mock_send.assert_called_once_with(
            chat_id=self.user.username,
            link=key.get_proxy_link(),
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && python manage.py test apps.payments.tests.test_notify_payment_service -v2`
Expected: `ImportError` — модуль не существует.

- [ ] **Step 3: Write implementation — create `src/apps/payments/services/notify_payment_service.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from apps.core.bot import TelegramBot

if TYPE_CHECKING:
    from apps.users.models import SystemUser
    from apps.vds.models import MTPRotoKey


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class NotifyPaymentService:
    """Отправляет пользователю прокси-ссылку через Telegram после оплаты."""

    def __call__(self, *, user: SystemUser, key: MTPRotoKey) -> None:
        TelegramBot.send_proxy_link(
            chat_id=user.username,
            link=key.get_proxy_link(),
        )


def get_notify_payment_service() -> NotifyPaymentService:
    return NotifyPaymentService()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && python manage.py test apps.payments.tests.test_notify_payment_service -v2`
Expected: 1 test passes.

---

### Task 9: Рефакторинг CreatePaymentService

**Files:**
- Modify: `src/apps/payments/services/create_payment_service.py`
- Modify: `src/apps/payments/services/__init__.py`
- Modify: `src/apps/payments/tests/test_create_payment_service.py`

- [ ] **Step 1: Rewrite `src/apps/payments/services/create_payment_service.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, final

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.service import log_service_error
from apps.payments.exceptions import BadPaymentData
from apps.payments.models import Payment
from apps.payments.services.extend_key_service import ExtendKeyService, get_extend_key_service
from apps.payments.services.notify_payment_service import NotifyPaymentService, get_notify_payment_service
from apps.users.selectors import get_user_by_username
from apps.vds.selectors import get_active_key
from apps.vds.services import get_issue_key_service

if TYPE_CHECKING:
    from apps.payments.services.dtos import CreatePaymentIn


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CreatePaymentService:
    """Оркестратор обработки платежа.

    Определяет стратегию: продлить существующий ключ или выдать новый.
    Создаёт запись Payment и делегирует нотификацию.

    Raises:
        BadPaymentData: если пользователь не найден по username.
    """

    extend_key_service: ExtendKeyService
    notify_service: NotifyPaymentService

    @log_service_error
    def __call__(self, *, payment: CreatePaymentIn) -> None:
        user = get_user_by_username(username=payment.username)
        if user is None:
            raise BadPaymentData(telegram_id=payment.username)

        active_key = get_active_key(user=user)

        with transaction.atomic():
            if active_key:
                self.extend_key_service(key=active_key)
                key = active_key
            else:
                key = get_issue_key_service()(
                    user=user,
                    expired_date=timezone.now() + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
                )

            Payment.objects.create(
                user=user,
                key=key,
                charge_id=payment.charge_id,
                provider=payment.provider,
            )

        self.notify_service(user=user, key=key)


def get_create_payment_service() -> CreatePaymentService:
    return CreatePaymentService(
        extend_key_service=get_extend_key_service(),
        notify_service=get_notify_payment_service(),
    )
```

- [ ] **Step 2: Update `src/apps/payments/services/__init__.py`**

```python
from apps.payments.services.create_payment_service import (
    CreatePaymentService,
    get_create_payment_service,
)
from apps.payments.services.extend_key_service import (
    ExtendKeyService,
    get_extend_key_service,
)
from apps.payments.services.notify_payment_service import (
    NotifyPaymentService,
    get_notify_payment_service,
)

__all__ = [
    "CreatePaymentService",
    "get_create_payment_service",
    "ExtendKeyService",
    "get_extend_key_service",
    "NotifyPaymentService",
    "get_notify_payment_service",
]
```

- [ ] **Step 3: Rewrite tests — `src/apps/payments/tests/test_create_payment_service.py`**

```python
from __future__ import annotations

from datetime import timedelta
from unittest import mock

import responses
from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import PaymentProviderEnum
from apps.payments.exceptions import BadPaymentData
from apps.payments.models import Payment
from apps.payments.services import get_create_payment_service
from apps.payments.services.dtos import CreatePaymentIn
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestCreatePaymentService(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()
        self.service = get_create_payment_service()

    def _make_payment(
        self,
        *,
        username: str | None = None,
        charge_id: str = "charge_1",
        provider: str = PaymentProviderEnum.YUKASSA,
    ) -> CreatePaymentIn:
        return CreatePaymentIn(
            username=username or self.user.username,
            charge_id=charge_id,
            provider=provider,
        )

    def _mock_vds_request(self) -> None:
        responses.add(
            method=responses.POST,
            url=self.vds.internal_url + "/api/users",
            json={
                "tls_domain": "petrovich.ru",
                "key": "testtoken123",
            },
        )

    @responses.activate
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    def test_creates_new_key_when_no_active_key(self, mock_send: mock.Mock, _task: mock.Mock) -> None:
        self._mock_vds_request()

        self.service(payment=self._make_payment(charge_id="charge_new"))

        self.assertEqual(MTPRotoKey.objects.count(), 1)
        key = MTPRotoKey.objects.first()
        self.assertEqual(key.user, self.user)
        self.assertEqual(key.tls_domain, "petrovich.ru")
        self.assertAlmostEqual(
            key.expired_date,
            timezone.now() + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )

        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.first()
        self.assertEqual(payment.key, key)
        self.assertEqual(payment.charge_id, "charge_new")
        self.assertEqual(payment.provider, PaymentProviderEnum.YUKASSA)

        mock_send.assert_called_once_with(
            chat_id=self.user.username,
            link=key.get_proxy_link(),
        )

    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    def test_extends_existing_active_key(self, mock_send: mock.Mock) -> None:
        existing_key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=15),
            was_deleted=False,
        )
        original_expired = existing_key.expired_date

        self.service(payment=self._make_payment(charge_id="charge_extend"))

        existing_key.refresh_from_db()
        self.assertAlmostEqual(
            existing_key.expired_date,
            original_expired + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )

        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.first()
        self.assertEqual(payment.key, existing_key)
        self.assertEqual(payment.charge_id, "charge_extend")

        mock_send.assert_called_once_with(
            chat_id=self.user.username,
            link=existing_key.get_proxy_link(),
        )

    @responses.activate
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    def test_creates_new_key_when_existing_key_is_expired(self, mock_send: mock.Mock, _task: mock.Mock) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() - timedelta(days=1),
            was_deleted=False,
        )
        self._mock_vds_request()

        self.service(payment=self._make_payment(charge_id="charge_expired"))

        self.assertEqual(MTPRotoKey.objects.count(), 1)
        new_key = MTPRotoKey.objects.first()
        self.assertAlmostEqual(
            new_key.expired_date,
            timezone.now() + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )
        self.assertEqual(Payment.objects.first().key, new_key)

    @responses.activate
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    def test_creates_new_key_when_existing_key_was_deleted(self, mock_send: mock.Mock, _task: mock.Mock) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=True,
        )
        self._mock_vds_request()

        self.service(payment=self._make_payment(charge_id="charge_deleted"))

        self.assertEqual(MTPRotoKey.objects.count(), 1)
        new_key = MTPRotoKey.objects.first()
        self.assertFalse(new_key.was_deleted)
        self.assertEqual(Payment.objects.first().key, new_key)

    @responses.activate
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    def test_stars_payment_issues_new_key(self, mock_send: mock.Mock, _task: mock.Mock) -> None:
        self._mock_vds_request()

        self.service(payment=self._make_payment(
            charge_id="stars_tx_123",
            provider=PaymentProviderEnum.STARS,
        ))

        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.first()
        self.assertEqual(payment.charge_id, "stars_tx_123")
        self.assertEqual(payment.provider, PaymentProviderEnum.STARS)

    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    def test_stars_payment_extends_existing_key(self, mock_send: mock.Mock) -> None:
        existing_key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=15),
            was_deleted=False,
        )
        original_expired = existing_key.expired_date

        self.service(payment=self._make_payment(
            charge_id="stars_tx_456",
            provider=PaymentProviderEnum.STARS,
        ))

        existing_key.refresh_from_db()
        self.assertAlmostEqual(
            existing_key.expired_date,
            original_expired + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )

        payment = Payment.objects.first()
        self.assertEqual(payment.charge_id, "stars_tx_456")
        self.assertEqual(payment.provider, PaymentProviderEnum.STARS)

    @mock.patch("apps.core.bot.TelegramBot.log_service_error")
    def test_raises_bad_payment_data_when_user_not_found(self, mock_log: mock.Mock) -> None:
        with self.assertRaises(BadPaymentData):
            self.service(payment=self._make_payment(username="nonexistent_user"))

        self.assertEqual(Payment.objects.count(), 0)
        mock_log.assert_called_once()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && python manage.py test apps.payments.tests.test_create_payment_service -v2`
Expected: 7 tests pass.

---

### Task 10: Обновление CreatePaymentView (DTO)

**Files:**
- Modify: `src/apps/payments/api/v1/views/create_payment_view.py`
- Modify: `src/apps/payments/tests/test_views/test_create_payment_view.py`

- [ ] **Step 1: Update `src/apps/payments/api/v1/views/create_payment_view.py`**

```python
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.api.v1.serializers import CreatePaymentSerializer
from apps.payments.services import get_create_payment_service
from apps.payments.services.dtos import CreatePaymentIn
from apps.users.permissions import BotAuthToken


class CreatePaymentView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = get_create_payment_service()
        service(payment=CreatePaymentIn(**serializer.validated_data))

        return Response(status=status.HTTP_200_OK)
```

- [ ] **Step 2: Run view tests to verify nothing broke**

Run: `cd src && python manage.py test apps.payments.tests.test_views.test_create_payment_view -v2`
Expected: 5 tests pass (existing tests unchanged, they test the HTTP contract).

---

### Task 11: Обновление ProductAPIView (ProductNotFound)

**Files:**
- Modify: `src/apps/payments/api/v1/views/get_product_view.py`
- Modify: `src/apps/payments/tests/test_views/test_get_product_view.py`

- [ ] **Step 1: Add failing test to `src/apps/payments/tests/test_views/test_get_product_view.py`**

Add this test method to the existing `TestGetProductView` class:

```python
    def test_returns_error_when_no_active_product(self) -> None:
        Product.objects.all().update(is_active=False)
        response = self.client.get(
            path=self.url,
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
```

Add the necessary import at the top of the file:

```python
from apps.payments.models import Product
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && python manage.py test apps.payments.tests.test_views.test_get_product_view.TestGetProductView.test_returns_error_when_no_active_product -v2`
Expected: FAIL — currently returns 200 with null fields.

- [ ] **Step 3: Update `src/apps/payments/api/v1/views/get_product_view.py`**

```python
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.api.v1.serializers import GetProductSerializer
from apps.payments.exceptions import ProductNotFound
from apps.payments.models import Product
from apps.users.permissions import BotAuthToken


class ProductAPIView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["get"]

    def get(self, request: Request) -> Response:
        product = Product.objects.active().first()
        if product is None:
            raise ProductNotFound(telegram_id="system")
        serializer = GetProductSerializer(instance=product)
        return Response(data=serializer.data, status=status.HTTP_200_OK)
```

Note: This also fixes the bad import `from gunicorn.http import Request` — replaced with `from rest_framework.request import Request`.

- [ ] **Step 4: Run all product view tests**

Run: `cd src && python manage.py test apps.payments.tests.test_views.test_get_product_view -v2`
Expected: 2 tests pass.

---

### Task 12: Удаление легаси + apps.py ready()

**Files:**
- Delete: `src/apps/payments/views.py`
- Modify: `src/apps/payments/apps.py`

- [ ] **Step 1: Delete `src/apps/payments/views.py`**

Run: `rm src/apps/payments/views.py`

- [ ] **Step 2: Update `src/apps/payments/apps.py`**

```python
from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    name = "apps.payments"

    def ready(self) -> None:
        import apps.payments.services  # noqa: F401
```

---

### Task 13: Финальная проверка — все тесты

**Files:** none (verification only)

- [ ] **Step 1: Run all payments tests**

Run: `cd src && python manage.py test apps.payments -v2`
Expected: All tests pass (service tests + view tests).

- [ ] **Step 2: Run selector tests**

Run: `cd src && python manage.py test apps.vds.tests.test_selectors apps.users.tests.test_selectors -v2`
Expected: 6 tests pass (4 vds + 2 users).

- [ ] **Step 3: Run full test suite**

Run: `cd src && python manage.py test -v2`
Expected: All project tests pass — no regressions.
