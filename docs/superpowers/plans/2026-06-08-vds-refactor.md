# VDS App Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `apps/vds/` to match the structure and conventions of the already-refactored `apps/users/` app.

**Architecture:** Move exceptions to a top-level `exceptions.py`, replace inline `Response` dataclasses with proper DTOs inheriting `BaseServiceDTO`, add `@final` to all services, add `__all__` to `services/__init__.py`, add `from __future__ import annotations` everywhere it's missing.

**Tech Stack:** Django, Python dataclasses, Celery

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `src/apps/vds/exceptions.py` | All VDS exceptions (infra + service) in one place |
| Create | `src/apps/vds/services/dtos/__init__.py` | Re-exports all DTOs |
| Create | `src/apps/vds/services/dtos/add_new_key_dto.py` | DTO for AddNewKeyInfraService response |
| Create | `src/apps/vds/services/dtos/update_key_dto.py` | DTO for UpdateKeyService response |
| Modify | `src/apps/vds/services/__init__.py` | Add `__all__` |
| Modify | `src/apps/vds/services/add_new_key_infra_service.py` | Use DTO, `@final`, import from `exceptions.py` |
| Modify | `src/apps/vds/services/update_key_infra_service.py` | Use DTO, `@final`, import from `exceptions.py` |
| Modify | `src/apps/vds/services/update_key_service.py` | Use DTO, `@final`, move exceptions out |
| Modify | `src/apps/vds/services/issue_key_service.py` | Add `@final` |
| Modify | `src/apps/vds/services/remove_key_infra_service.py` | Add `@final`, import from `exceptions.py` |
| Delete | `src/apps/vds/services/exceptions.py` | Replaced by top-level `exceptions.py` |
| Modify | `src/apps/vds/tests/test_services/test_add_user_service.py` | Update import path for exceptions |

---

### Task 1: Create top-level `exceptions.py` and move all exceptions

**Files:**
- Create: `src/apps/vds/exceptions.py`
- Modify: `src/apps/vds/services/add_new_key_infra_service.py`
- Modify: `src/apps/vds/services/update_key_infra_service.py`
- Modify: `src/apps/vds/services/remove_key_infra_service.py`
- Modify: `src/apps/vds/services/update_key_service.py`
- Modify: `src/apps/vds/tests/test_services/test_add_user_service.py`
- Delete: `src/apps/vds/services/exceptions.py`

- [ ] **Step 1: Create `src/apps/vds/exceptions.py`**

Consolidate all 4 exceptions (2 infra from `services/exceptions.py`, 2 service from `update_key_service.py`):

```python
from __future__ import annotations

from apps.core.exceptions import BaseInfraError, BaseServiceError


class VDSNotAvailable(BaseInfraError):
    """VDS not available"""


class VDSConnectionLimit(BaseInfraError):
    """VDS connection limit"""


class KeyDoesNotExist(BaseServiceError):
    """🔒 У вас нет активного ключа. Если вы думаете, что это ошибка, пожалуйста, свяжитесь с нами через сообщения канала — @mtproto_keys."""


class TooManyRequests(BaseServiceError):
    """🔒 Пожалуйста, подождите 5 минут с последнего обновления."""
```

- [ ] **Step 2: Update imports in `add_new_key_infra_service.py`**

Change:
```python
from apps.vds.services.exceptions import VDSConnectionLimit, VDSNotAvailable
```
To:
```python
from apps.vds.exceptions import VDSConnectionLimit, VDSNotAvailable
```

- [ ] **Step 3: Update imports in `update_key_infra_service.py`**

Change:
```python
from apps.vds.services.exceptions import VDSNotAvailable
```
To:
```python
from apps.vds.exceptions import VDSNotAvailable
```

- [ ] **Step 4: Update imports in `remove_key_infra_service.py`**

Change:
```python
from apps.vds.services.exceptions import VDSNotAvailable
```
To:
```python
from apps.vds.exceptions import VDSNotAvailable
```

- [ ] **Step 5: Update imports in `update_key_service.py`**

Remove the two inline exception classes (`KeyDoesNotExist`, `TooManyRequests`) and replace with import:

Remove:
```python
from apps.core.exceptions import BaseServiceError

class KeyDoesNotExist(BaseServiceError):
    """..."""

class TooManyRequests(BaseServiceError):
    """..."""
```

Add:
```python
from apps.vds.exceptions import KeyDoesNotExist, TooManyRequests
```

- [ ] **Step 6: Update test import in `test_add_user_service.py`**

Change:
```python
from apps.vds.services.exceptions import VDSConnectionLimit
```
To:
```python
from apps.vds.exceptions import VDSConnectionLimit
```

- [ ] **Step 7: Delete `src/apps/vds/services/exceptions.py`**

Remove the file — all its contents are now in `src/apps/vds/exceptions.py`.

- [ ] **Step 8: Run tests**

Run: `make test ARGS="apps.vds"`
Expected: All existing VDS tests pass.

---

### Task 2: Create DTOs for infra service responses

**Files:**
- Create: `src/apps/vds/services/dtos/__init__.py`
- Create: `src/apps/vds/services/dtos/add_new_key_dto.py`
- Create: `src/apps/vds/services/dtos/update_key_dto.py`

- [ ] **Step 1: Create `src/apps/vds/services/dtos/add_new_key_dto.py`**

This replaces the `Response` dataclass in `add_new_key_infra_service.py` and `update_key_infra_service.py` (both have the same shape: `key` + `tls_domain`):

```python
from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class VDSKeyResponseOut(BaseServiceDTO):
    """Ответ VDS-сервера при создании/обновлении ключа."""

    key: str
    tls_domain: str
```

- [ ] **Step 2: Create `src/apps/vds/services/dtos/update_key_dto.py`**

This replaces the `Response` dataclass in `update_key_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class UpdateKeyOut(BaseServiceDTO):
    """Результат обновления ключа: ссылка и дата окончания."""

    link: str
    expired_date: str
```

- [ ] **Step 3: Create `src/apps/vds/services/dtos/__init__.py`**

```python
from apps.vds.services.dtos.add_new_key_dto import VDSKeyResponseOut
from apps.vds.services.dtos.update_key_dto import UpdateKeyOut

__all__ = [
    "VDSKeyResponseOut",
    "UpdateKeyOut",
]
```

- [ ] **Step 4: Run tests**

Run: `make test ARGS="apps.vds"`
Expected: All pass (DTOs created but not yet wired in).

---

### Task 3: Wire DTOs into services and add `@final`

**Files:**
- Modify: `src/apps/vds/services/add_new_key_infra_service.py`
- Modify: `src/apps/vds/services/update_key_infra_service.py`
- Modify: `src/apps/vds/services/update_key_service.py`
- Modify: `src/apps/vds/services/issue_key_service.py`
- Modify: `src/apps/vds/services/remove_key_infra_service.py`

- [ ] **Step 1: Refactor `add_new_key_infra_service.py`**

Full file after changes:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import final

import requests
from django.conf import settings

from apps.core.decorators import log_infra_error
from apps.vds.exceptions import VDSConnectionLimit, VDSNotAvailable
from apps.vds.models import MTPRotoKey, VDSInstance
from apps.vds.services.dtos import VDSKeyResponseOut
from apps.vds.tasks import add_key_to_another_vds_instances_task


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class AddNewKeyInfraService:
    @log_infra_error
    def __call__(self, *, server: VDSInstance, username: str) -> VDSKeyResponseOut | None:
        self._check_vds_limit(server=server, username=username)
        try:
            secret = str(os.urandom(16).hex())
            response = requests.post(
                url=f"{server.internal_url}/api/users",
                json={"username": username, "secret": secret},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            MTPRotoKey.objects.filter(user__username=username).delete()
            add_key_to_another_vds_instances_task.delay(
                exclude=server.pk,
                username=username,
                secret=secret,
            )
            return VDSKeyResponseOut(**response.json())
        except Exception as exc:
            raise VDSNotAvailable(
                method="add-user",
                base_error=str(exc),
                telegram_id=username,
                server=dict(
                    id=server.pk,
                    name=server.name,
                    ip=server.ip_address,
                    port=server.port,
                    url=server.external_url,
                ),
            )

    @classmethod
    def _check_vds_limit(cls, *, server: VDSInstance, username: str) -> None:
        if not server.is_available():
            raise VDSConnectionLimit(
                method="add-user",
                telegram_id=username,
                server=dict(
                    id=server.pk,
                    name=server.name,
                    ip=server.ip_address,
                    port=server.port,
                    url=server.external_url,
                ),
            )


def get_add_new_key_service_factory() -> AddNewKeyInfraService:
    return AddNewKeyInfraService()
```

- [ ] **Step 2: Refactor `update_key_infra_service.py`**

Full file after changes:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import final

import requests
from django.conf import settings

from apps.core.decorators import log_infra_error
from apps.vds.exceptions import VDSNotAvailable
from apps.vds.models import MTPRotoKey
from apps.vds.services.dtos import VDSKeyResponseOut
from apps.vds.tasks import (
    add_key_to_another_vds_instances_task,
    remove_key_from_another_vds_instances_task,
)


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class UpdateKeyInfraService:
    @log_infra_error
    def __call__(self, *, old_key: MTPRotoKey, username: str) -> VDSKeyResponseOut | None:
        try:
            secret = str(os.urandom(16).hex())
            response = requests.patch(
                url=f"{old_key.vds.internal_url}/api/users",
                json={"username": username, "secret": secret},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            add_key_to_another_vds_instances_task.delay(
                exclude=old_key.vds.pk, username=username, secret=secret
            )
            return VDSKeyResponseOut(**response.json())
        except Exception as exc:
            raise VDSNotAvailable(
                method="add-user",
                base_error=str(exc),
                telegram_id=username,
                server=dict(
                    id=old_key.vds.pk,
                    name=old_key.vds.name,
                    ip=old_key.vds.ip_address,
                    port=old_key.vds.port,
                    url=old_key.vds.external_url,
                ),
            )


def get_update_key_infra_service() -> UpdateKeyInfraService:
    return UpdateKeyInfraService()
```

- [ ] **Step 3: Refactor `update_key_service.py`**

Full file after changes:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import final

from django.db import transaction
from django.utils import timezone

from apps.core.decorators import log_service_error
from apps.vds.exceptions import KeyDoesNotExist, TooManyRequests
from apps.vds.models import MTPRotoKey
from apps.vds.services import get_update_key_infra_service
from apps.vds.services.dtos import UpdateKeyOut


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class UpdateKeyService:
    @log_service_error
    def __call__(self, *, username: str) -> UpdateKeyOut | None:
        key = MTPRotoKey.objects.filter(
            user__username=username, is_active=True, was_deleted=False
        ).first()
        if key is None:
            raise KeyDoesNotExist(telegram_id=username)

        if key.last_update and (
            key.last_update + timedelta(minutes=5) > timezone.now()
        ):
            raise TooManyRequests(telegram_id=username)

        with transaction.atomic():

            infra = get_update_key_infra_service()
            response = infra(username=username, old_key=key)

            key.vds = key.vds
            key.token = response.key
            key.tls_domain = response.tls_domain
            key.node_number = key.vds.name
            key.last_update = timezone.now()
            key.was_deleted = False
            key.is_active = True
            key.save(
                update_fields=[
                    "token",
                    "tls_domain",
                    "node_number",
                    "vds",
                    "last_update",
                    "was_deleted",
                    "is_active",
                ]
            )

            MTPRotoKey.objects.filter(user__username=username).exclude(
                pk=key.pk
            ).delete()
        return UpdateKeyOut(
            link=key.get_proxy_link(),
            expired_date=key.expired_date.date().strftime("%d.%m.%y"),
        )


def get_update_key_service() -> UpdateKeyService:
    return UpdateKeyService()
```

- [ ] **Step 4: Add `@final` to `issue_key_service.py`**

Add `from typing import final` import and `@final` decorator:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from apps.vds.models import MTPRotoKey, VDSInstance
from apps.vds.services.add_new_key_infra_service import get_add_new_key_service_factory

if TYPE_CHECKING:
    from datetime import datetime

    from apps.users.models import SystemUser


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class IssueKeyService:
    """Выдаёт новый MTPRoto-ключ на наименее загруженном VDS."""

    def __call__(
        self,
        *,
        user: SystemUser,
        expired_date: datetime,
    ) -> MTPRotoKey:
        server = VDSInstance.objects.get_least_populated()
        response = get_add_new_key_service_factory()(
            server=server,
            username=str(user.username),
        )
        return MTPRotoKey.objects.create(
            vds=server,
            user=user,
            token=response.key,
            tls_domain=response.tls_domain,
            node_number=server.name,
            expired_date=expired_date,
        )


def get_issue_key_service() -> IssueKeyService:
    return IssueKeyService()
```

- [ ] **Step 5: Add `@final` and `from __future__ import annotations` to `remove_key_infra_service.py`**

```python
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import final

import requests
from django.conf import settings
from django.db.models import QuerySet

from apps.core.decorators import log_infra_error
from apps.vds.exceptions import VDSNotAvailable
from apps.vds.models import MTPRotoKey, VDSInstance


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class RemoveUserKeyInfraService:
    @log_infra_error
    def __call__(self, *, server: VDSInstance, keys: QuerySet[MTPRotoKey]) -> None:
        keys = deepcopy(keys)
        usernames = []
        try:
            usernames = list(
                keys.values_list("user__username", flat=True).distinct()
            )
            response = requests.delete(
                f"{server.internal_url}/api/users",
                json={"usernames": usernames},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except Exception as exc:
            raise VDSNotAvailable(
                method="remove-user",
                telegram_id=usernames,
                base_error=str(exc),
                usernames=usernames,
                server=dict(
                    id=server.pk,
                    name=server.name,
                    ip=server.ip_address,
                    port=server.port,
                    url=server.external_url,
                ),
            )


def get_remove_user_key_infra_service() -> RemoveUserKeyInfraService:
    return RemoveUserKeyInfraService()
```

- [ ] **Step 6: Run tests**

Run: `make test ARGS="apps.vds"`
Expected: All pass.

---

### Task 4: Update `services/__init__.py` with `__all__`

**Files:**
- Modify: `src/apps/vds/services/__init__.py`

- [ ] **Step 1: Rewrite `services/__init__.py`**

```python
from apps.vds.services.add_new_key_infra_service import (
    AddNewKeyInfraService,
    get_add_new_key_service_factory,
)
from apps.vds.services.issue_key_service import (
    IssueKeyService,
    get_issue_key_service,
)
from apps.vds.services.remove_key_infra_service import (
    RemoveUserKeyInfraService,
    get_remove_user_key_infra_service,
)
from apps.vds.services.update_key_infra_service import (
    UpdateKeyInfraService,
    get_update_key_infra_service,
)
from apps.vds.services.update_key_service import (
    UpdateKeyService,
    get_update_key_service,
)

__all__ = [
    "AddNewKeyInfraService",
    "get_add_new_key_service_factory",
    "IssueKeyService",
    "get_issue_key_service",
    "RemoveUserKeyInfraService",
    "get_remove_user_key_infra_service",
    "UpdateKeyInfraService",
    "get_update_key_infra_service",
    "UpdateKeyService",
    "get_update_key_service",
]
```

- [ ] **Step 2: Run tests**

Run: `make test ARGS="apps.vds"`
Expected: All pass.

---

### Task 5: Run full test suite

- [ ] **Step 1: Run all tests to check for regressions**

Run: `make test`
Expected: All tests pass. The refactoring is purely structural — no logic changed. External consumers (`apps.users`, `apps.payments`, `apps.users.api`) import from `apps.vds.services` (the `__init__.py`), which still re-exports the same names.
