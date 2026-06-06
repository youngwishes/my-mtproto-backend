# Рефакторинг apps/users/ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Привести приложение `apps/users/` к паттернам SOLID/DRY/DDD по аналогии с `apps/payments/`: вынести исключения, enum, расширить селекторы, ввести DTO, добавить `@final` + DI в сервисы.

**Architecture:** Сервисы — frozen dataclass с `@final`. ORM-запросы вынесены в `selectors.py`. Исключения и enum — в отдельных модулях. Выходные данные — DTO, наследующие `BaseServiceDTO`. Зависимость на `IssueKeyService` инъецируется через поля dataclass, фабрики собирают граф. Существующие тесты (через views) должны продолжать проходить без изменений.

**Tech Stack:** Django 6, DRF, Python 3.13, factory_boy, responses, unittest.mock

**Reference:** `apps/payments/` — уже отрефакторено по этим паттернам.

---

## File Structure

```
apps/users/
├── models.py                          # без изменений
├── enums.py                           # NEW — FreeAvailable enum
├── exceptions.py                      # NEW — AlreadyUsedFree, AlreadyUsedProgram, NotEnoughReferrals
├── selectors.py                       # MODIFY — добавить 3 новых селектора
├── permissions.py                     # без изменений
├── apps.py                            # MODIFY — добавить ready()
├── admin.py                           # без изменений
├── tasks.py                           # без изменений
├── api/                               # views и serializers — минимальные правки
│   └── v1/
│       ├── views/
│       │   ├── first_free_link_view.py   # MODIFY — импорт CheckFirstFreeLinkIn
│       │   ├── referral_cabinet_view.py  # без изменений
│       │   └── update_key_view.py        # без изменений
│       └── serializers/                  # без изменений
├── services/
│   ├── __init__.py                       # MODIFY — обновить экспорты
│   ├── first_free_link_service.py        # MODIFY — @final, DI, selectors, DTO
│   ├── check_first_free_link_service.py  # MODIFY — @final, selectors, DTO
│   ├── referral_cabinet_service.py       # MODIFY — @final, selectors, DTO
│   ├── get_free_link_via_referrals.py    # MODIFY — @final, DI, selectors, DTO
│   └── dtos/
│       ├── __init__.py                   # NEW
│       ├── check_first_free_link_dto.py  # NEW — CheckFirstFreeLinkIn
│       ├── issued_key_dto.py             # NEW — IssuedKeyOut (shared)
│       └── referral_cabinet_dto.py       # NEW — ReferralCabinetOut
└── tests/
    ├── test_selectors.py                 # MODIFY — добавить тесты новых селекторов
    └── ...                               # остальные тесты без изменений
```

---

### Task 1: Создание `exceptions.py` и `enums.py`

**Files:**
- Create: `src/apps/users/exceptions.py`
- Create: `src/apps/users/enums.py`

- [ ] **Step 1: Create `src/apps/users/exceptions.py`**

```python
from apps.core.service import BaseServiceError


class AlreadyUsedFree(BaseServiceError):
    """🔒 Вы уже получили беплатную ссылку. Если она не работает — напишите нам в личные сообщения канала @mtproto_keys."""


class AlreadyUsedProgram(BaseServiceError):
    """🔒 Вы уже воспользовались реферальной программой."""


class NotEnoughReferrals(BaseServiceError):
    """🔒 Пригласите как минимум 5 пользователей. Используйте для этого вашу реферальную ссылку. Каждый приглашенный пользователь должен воспользоваться бесплатным периодом в 14 дней по вашей реферальной ссылке."""
```

- [ ] **Step 2: Create `src/apps/users/enums.py`**

```python
from enum import StrEnum


class FreeAvailable(StrEnum):
    MONTH = "MONTH"
    TWO_WEEK = "TWO_WEEK"
    WEEK = "WEEK"
    NOT_AVAILABLE = "NOT_AVAILABLE"
```

- [ ] **Step 3: Verify imports**

Run: `cd src && python -c "from apps.users.exceptions import AlreadyUsedFree, AlreadyUsedProgram, NotEnoughReferrals; print('OK')"`
Run: `cd src && python -c "from apps.users.enums import FreeAvailable; print(FreeAvailable.MONTH)"`

---

### Task 2: Расширение `selectors.py` + тесты

**Files:**
- Modify: `src/apps/users/selectors.py`
- Modify: `src/apps/users/tests/test_selectors.py`

- [ ] **Step 1: Write failing tests — добавить в `src/apps/users/tests/test_selectors.py`**

```python
from __future__ import annotations

from django.test import TestCase

from apps.users.selectors import (
    get_user_by_username,
    get_free_used_count,
    get_total_referrals_count,
    get_active_referrals_count,
)
from apps.users.tests.factories import SystemUserFactory


class TestGetUserByUsername(TestCase):
    def test_returns_user_when_exists(self) -> None:
        user = SystemUserFactory(username="123456")
        result = get_user_by_username(username="123456")
        self.assertEqual(result, user)

    def test_returns_none_when_not_found(self) -> None:
        result = get_user_by_username(username="nonexistent")
        self.assertIsNone(result)


class TestGetFreeUsedCount(TestCase):
    def test_returns_zero_when_no_users(self) -> None:
        self.assertEqual(get_free_used_count(), 0)

    def test_returns_count_of_users_with_free_used(self) -> None:
        SystemUserFactory(first_month_free_used=True)
        SystemUserFactory(first_month_free_used=True)
        SystemUserFactory(first_month_free_used=False)
        self.assertEqual(get_free_used_count(), 2)


class TestGetTotalReferralsCount(TestCase):
    def test_returns_zero_when_no_referrals(self) -> None:
        self.assertEqual(get_total_referrals_count(username="user1"), 0)

    def test_returns_count_of_invited_users(self) -> None:
        SystemUserFactory(invited_from_username="user1")
        SystemUserFactory(invited_from_username="user1")
        SystemUserFactory(invited_from_username="other")
        self.assertEqual(get_total_referrals_count(username="user1"), 2)


class TestGetActiveReferralsCount(TestCase):
    def test_returns_zero_when_no_active_referrals(self) -> None:
        SystemUserFactory(invited_from_username="user1", referral_activated=False)
        self.assertEqual(get_active_referrals_count(username="user1"), 0)

    def test_returns_count_of_active_referrals(self) -> None:
        SystemUserFactory(invited_from_username="user1", referral_activated=True)
        SystemUserFactory(invited_from_username="user1", referral_activated=True)
        SystemUserFactory(invited_from_username="user1", referral_activated=False)
        self.assertEqual(get_active_referrals_count(username="user1"), 2)
```

- [ ] **Step 2: Run tests to verify new ones fail**

Run: `cd src && python manage.py test apps.users.tests.test_selectors -v2`
Expected: `ImportError` — `get_free_used_count` не существует.

- [ ] **Step 3: Update `src/apps/users/selectors.py`**

```python
from __future__ import annotations

from apps.users.models import SystemUser


def get_user_by_username(*, username: str) -> SystemUser | None:
    """Находит пользователя по Telegram ID (хранится в поле username)."""
    return SystemUser.objects.filter(username=username).first()


def get_free_used_count() -> int:
    """Количество пользователей, использовавших бесплатный период."""
    return SystemUser.objects.filter(first_month_free_used=True).count()


def get_total_referrals_count(*, username: str) -> int:
    """Общее количество приглашённых пользователей."""
    return SystemUser.objects.filter(invited_from_username=username).count()


def get_active_referrals_count(*, username: str) -> int:
    """Количество приглашённых пользователей, активировавших реферал."""
    return SystemUser.objects.filter(
        invited_from_username=username,
        referral_activated=True,
    ).count()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && python manage.py test apps.users.tests.test_selectors -v2`
Expected: 8 tests pass.

---

### Task 3: Создание DTOs

**Files:**
- Create: `src/apps/users/services/dtos/__init__.py`
- Create: `src/apps/users/services/dtos/check_first_free_link_dto.py`
- Create: `src/apps/users/services/dtos/issued_key_dto.py`
- Create: `src/apps/users/services/dtos/referral_cabinet_dto.py`

- [ ] **Step 1: Create `src/apps/users/services/dtos/check_first_free_link_dto.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class CheckFirstFreeLinkIn(BaseServiceDTO):
    """Входные данные для проверки доступности бесплатного периода."""

    username: str
    telegram_username: str
    invited_from_username: str | None = None
```

- [ ] **Step 2: Create `src/apps/users/services/dtos/issued_key_dto.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class IssuedKeyOut(BaseServiceDTO):
    """Результат выдачи ключа: ссылка и дата окончания."""

    expired_date: str
    link: str
```

- [ ] **Step 3: Create `src/apps/users/services/dtos/referral_cabinet_dto.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class ReferralCabinetOut(BaseServiceDTO):
    """Данные реферального кабинета пользователя."""

    total_referrals_count: int | None
    active_referrals_count: int | None
    referral_link: str | None
    link_activated_count: int | None
```

- [ ] **Step 4: Create `src/apps/users/services/dtos/__init__.py`**

```python
from apps.users.services.dtos.check_first_free_link_dto import CheckFirstFreeLinkIn
from apps.users.services.dtos.issued_key_dto import IssuedKeyOut
from apps.users.services.dtos.referral_cabinet_dto import ReferralCabinetOut

__all__ = [
    "CheckFirstFreeLinkIn",
    "IssuedKeyOut",
    "ReferralCabinetOut",
]
```

- [ ] **Step 5: Verify imports**

Run: `cd src && python -c "from apps.users.services.dtos import CheckFirstFreeLinkIn, IssuedKeyOut, ReferralCabinetOut; print('OK')"`

---

### Task 4: Рефакторинг `FirstFreeLinkService`

**Files:**
- Modify: `src/apps/users/services/first_free_link_service.py`

- [ ] **Step 1: Rewrite `src/apps/users/services/first_free_link_service.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, final

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.service import log_service_error
from apps.users.exceptions import AlreadyUsedFree
from apps.users.selectors import get_free_used_count
from apps.users.services.dtos import IssuedKeyOut

if TYPE_CHECKING:
    from apps.users.models import SystemUser
    from apps.vds.services.issue_key_service import IssueKeyService


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FirstFreeLinkService:
    """Выдаёт бесплатный ключ пользователю.

    Длительность зависит от условий:
    - 30 дней — стандарт
    - 7 дней — если лимит бесплатных ключей исчерпан
    - 14 дней — если пользователь пришёл по реферальной ссылке
    """

    issue_key_service: IssueKeyService

    @log_service_error
    def __call__(self, *, username: str) -> IssuedKeyOut:
        user, _ = SystemUser.objects.get_or_create(username=username)

        if user.first_month_free_used:
            raise AlreadyUsedFree(telegram_id=username)

        expired_date = self._resolve_expired_date(user=user)

        with transaction.atomic():
            mtproto_key = self.issue_key_service(user=user, expired_date=expired_date)
            user.first_month_free_used = True
            if user.invited_from_username:
                user.referral_activated = True
            user.save(update_fields=["first_month_free_used", "referral_activated"])

        return IssuedKeyOut(
            link=mtproto_key.get_proxy_link(),
            expired_date=expired_date.date().strftime("%d.%m.%y"),
        )

    def _resolve_expired_date(self, *, user: SystemUser) -> timezone.datetime:
        expired_date = timezone.now() + timedelta(days=30)

        if get_free_used_count() >= settings.FIRST_MONTH_LIMIT:
            expired_date = timezone.now() + timedelta(days=7)

        if user.invited_from_username:
            expired_date = timezone.now() + timedelta(days=14)

        return expired_date


def get_first_free_link_service() -> FirstFreeLinkService:
    from apps.vds.services import get_issue_key_service

    return FirstFreeLinkService(
        issue_key_service=get_issue_key_service(),
    )
```

- [ ] **Step 2: Run existing tests to verify nothing broke**

Run: `cd src && python manage.py test apps.users.tests.test_first_free_link -v2`
Expected: All 6 tests pass.

---

### Task 5: Рефакторинг `CheckFirstFreeLinkService`

**Files:**
- Modify: `src/apps/users/services/check_first_free_link_service.py`

- [ ] **Step 1: Rewrite `src/apps/users/services/check_first_free_link_service.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import final

from django.conf import settings

from apps.core.service import log_service_error
from apps.users.enums import FreeAvailable
from apps.users.models import SystemUser
from apps.users.selectors import get_free_used_count
from apps.users.services.dtos import CheckFirstFreeLinkIn


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CheckFirstFreeLinkService:
    """Проверяет доступность бесплатного периода для пользователя.

    Побочный эффект: создаёт пользователя, если его нет,
    и обновляет telegram_username.
    """

    @log_service_error
    def __call__(self, *, data: CheckFirstFreeLinkIn) -> FreeAvailable:
        user = self._ensure_user(data=data)

        if user.first_month_free_used:
            return FreeAvailable.NOT_AVAILABLE

        if get_free_used_count() >= settings.FIRST_MONTH_LIMIT:
            if user.invited_from_username:
                return FreeAvailable.TWO_WEEK
            return FreeAvailable.WEEK

        return FreeAvailable.MONTH

    def _ensure_user(self, *, data: CheckFirstFreeLinkIn) -> SystemUser:
        try:
            user = SystemUser.objects.get(username=data.username)
            if not user.telegram_username:
                user.telegram_username = data.telegram_username
                user.save(update_fields=["telegram_username"])
        except SystemUser.DoesNotExist:
            user = SystemUser.objects.create(
                username=data.username,
                telegram_username=data.telegram_username,
                invited_from_username=data.invited_from_username,
            )
        return user


def get_check_first_free_link_service() -> CheckFirstFreeLinkService:
    return CheckFirstFreeLinkService()
```

- [ ] **Step 2: Update view — `src/apps/users/api/v1/views/first_free_link_view.py`**

Сигнатура `CheckFirstFreeLinkService.__call__` изменилась: теперь принимает `data: CheckFirstFreeLinkIn` вместо отдельных аргументов. Нужно обновить вызов в view:

```python
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.bot import notify_bad_request
from apps.users.api.v1.serializers import (
    CheckFirstFreeLinkSerializer,
    FirstFreeLinkSerializer,
)
from apps.users.permissions import BotAuthToken
from apps.users.services import get_first_free_link_service
from apps.users.services.check_first_free_link_service import (
    get_check_first_free_link_service,
)
from apps.users.services.dtos import CheckFirstFreeLinkIn


class CreateFirstFreeLinkView(APIView):
    permission_classes = (BotAuthToken,)

    @notify_bad_request
    def post(self, request: Request) -> Response:
        serializer = FirstFreeLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = get_first_free_link_service()
        result = service(username=serializer.validated_data["username"])

        return Response(data=result.asdict(), status=status.HTTP_200_OK)


class CheckFirstFreeLinkView(APIView):
    permission_classes = (BotAuthToken,)

    @notify_bad_request
    def post(self, request: Request) -> Response:
        serializer = CheckFirstFreeLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = get_check_first_free_link_service()
        result = service(
            data=CheckFirstFreeLinkIn(
                username=serializer.validated_data["username"],
                telegram_username=serializer.validated_data.get("telegram_username", ""),
                invited_from_username=serializer.validated_data.get("invited_from_username") or None,
            ),
        )
        return Response(
            data={"available_free_period": result},
            status=status.HTTP_200_OK,
        )
```

- [ ] **Step 3: Run existing tests**

Run: `cd src && python manage.py test apps.users.tests.test_check_first_free_link -v2`
Expected: All 6 tests pass.

---

### Task 6: Рефакторинг `ReferralCabinetService`

**Files:**
- Modify: `src/apps/users/services/referral_cabinet_service.py`

- [ ] **Step 1: Rewrite `src/apps/users/services/referral_cabinet_service.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import final

from apps.users.selectors import (
    get_active_referrals_count,
    get_total_referrals_count,
    get_user_by_username,
)
from apps.users.services.dtos import ReferralCabinetOut


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReferralCabinetService:
    """Возвращает данные реферального кабинета пользователя."""

    def __call__(self, *, username: str) -> ReferralCabinetOut:
        user = get_user_by_username(username=username)

        if user is None:
            return ReferralCabinetOut(
                total_referrals_count=None,
                active_referrals_count=None,
                referral_link=None,
                link_activated_count=None,
            )

        return ReferralCabinetOut(
            total_referrals_count=get_total_referrals_count(username=username),
            active_referrals_count=get_active_referrals_count(username=username),
            referral_link=user.referral_link,
            link_activated_count=user.referral_link_activated_count,
        )


def get_referral_cabinet_service() -> ReferralCabinetService:
    return ReferralCabinetService()
```

- [ ] **Step 2: Run existing tests**

Run: `cd src && python manage.py test apps.users.tests.test_referral_cabinet_view -v2`
Expected: All 3 tests pass.

---

### Task 7: Рефакторинг `GetReferralVDSLinkService`

**Files:**
- Modify: `src/apps/users/services/get_free_link_via_referrals.py`

- [ ] **Step 1: Rewrite `src/apps/users/services/get_free_link_via_referrals.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, final

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.service import log_service_error
from apps.users.exceptions import AlreadyUsedProgram, NotEnoughReferrals
from apps.users.models import SystemUser
from apps.users.selectors import get_active_referrals_count
from apps.users.services.dtos import IssuedKeyOut

if TYPE_CHECKING:
    from apps.vds.services.issue_key_service import IssueKeyService


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class GetReferralVDSLinkService:
    """Выдаёт бесплатный ключ по реферальной программе.

    Условия: пользователь не использовал программу ранее,
    и у него >= INVITE_MUST_COUNT активных рефералов.
    """

    issue_key_service: IssueKeyService

    @log_service_error
    def __call__(self, *, username: str) -> IssuedKeyOut:
        user = SystemUser.objects.get(username=username)

        if user.referral_link_activated_count >= settings.REFERRAL_LINKS_LIMIT:
            raise AlreadyUsedProgram(telegram_id=username)

        if get_active_referrals_count(username=username) < settings.INVITE_MUST_COUNT:
            raise NotEnoughReferrals(telegram_id=username)

        expired_date = timezone.now() + timedelta(days=14)

        with transaction.atomic():
            mtproto_key = self.issue_key_service(user=user, expired_date=expired_date)
            user.referral_link_activated_count += 1
            user.save(update_fields=["referral_link_activated_count"])

        return IssuedKeyOut(
            link=mtproto_key.get_proxy_link(),
            expired_date=expired_date.date().strftime("%d.%m.%y"),
        )


def get_referral_vds_link_service() -> GetReferralVDSLinkService:
    from apps.vds.services import get_issue_key_service

    return GetReferralVDSLinkService(
        issue_key_service=get_issue_key_service(),
    )
```

- [ ] **Step 2: Run existing tests**

Run: `cd src && python manage.py test apps.users.tests.test_get_referral_link_view -v2`
Expected: All 4 tests pass.

---

### Task 8: Обновление `services/__init__.py` и `apps.py`

**Files:**
- Modify: `src/apps/users/services/__init__.py`
- Modify: `src/apps/users/apps.py`

- [ ] **Step 1: Rewrite `src/apps/users/services/__init__.py`**

```python
from apps.users.services.first_free_link_service import (
    FirstFreeLinkService,
    get_first_free_link_service,
)
from apps.users.services.check_first_free_link_service import (
    CheckFirstFreeLinkService,
    get_check_first_free_link_service,
)
from apps.users.services.referral_cabinet_service import (
    ReferralCabinetService,
    get_referral_cabinet_service,
)
from apps.users.services.get_free_link_via_referrals import (
    GetReferralVDSLinkService,
    get_referral_vds_link_service,
)

__all__ = [
    "FirstFreeLinkService",
    "get_first_free_link_service",
    "CheckFirstFreeLinkService",
    "get_check_first_free_link_service",
    "ReferralCabinetService",
    "get_referral_cabinet_service",
    "GetReferralVDSLinkService",
    "get_referral_vds_link_service",
]
```

- [ ] **Step 2: Update `src/apps/users/apps.py`**

```python
from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "apps.users"

    def ready(self) -> None:
        import apps.users.services  # noqa: F401
```

---

### Task 9: Финальная проверка — все тесты

**Files:** нет (только верификация)

- [ ] **Step 1: Run all users tests**

Run: `cd src && python manage.py test apps.users -v2`
Expected: All tests pass.

- [ ] **Step 2: Run full test suite**

Run: `cd src && python manage.py test -v2`
Expected: All project tests pass — no regressions.
