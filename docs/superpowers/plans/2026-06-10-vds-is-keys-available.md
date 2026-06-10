# VDSInstance.is_keys_available — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `is_keys_available` field to `VDSInstance` so servers can be excluded from key issuance/reissuance routing; fix a latent bug where key-update replication incorrectly used POST instead of PATCH.

**Architecture:** The field is enforced inside `VDSQuerySet.order_by_population()` — all selection paths (new key, reissue) go through this method so no caller needs changing. A new `UpdateKeyOnAnotherVdsInfraService` provides PATCH-based replication for update flows. `UpdateKeyService` gains `get_least_populated_vds()` selection so migration to a new server happens automatically when the current server has `is_keys_available=False`.

**Tech Stack:** Django ORM, factory_boy, `responses` (HTTP mocking), Celery

---

### Task 1: Add `is_keys_available` field and QuerySet filter

**Files:**
- Modify: `src/apps/vds/models.py`
- Create: `src/apps/vds/tests/test_models.py`
- Create: `src/apps/vds/migrations/0014_vdsinstance_is_keys_available.py` (auto-generated)

- [ ] **Step 1: Write the failing tests**

```python
# src/apps/vds/tests/test_models.py
from __future__ import annotations

from django.test import TestCase

from apps.vds.selectors import get_least_populated_vds
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestVDSQuerySet(TestCase):
    def test_get_least_populated_excludes_is_keys_available_false(self) -> None:
        VDSInstanceFactory(is_keys_available=False)
        available = VDSInstanceFactory(is_keys_available=True)

        result = get_least_populated_vds()

        self.assertEqual(result, available)

    def test_get_least_populated_picks_least_loaded_among_available(self) -> None:
        server_1 = VDSInstanceFactory(is_keys_available=True)
        server_2 = VDSInstanceFactory(is_keys_available=True)
        for _ in range(3):
            MTPRotoKeyFactory(vds=server_1)

        result = get_least_populated_vds()

        self.assertEqual(result, server_2)

    def test_get_least_populated_returns_none_when_all_have_keys_unavailable(self) -> None:
        VDSInstanceFactory(is_keys_available=False)

        result = get_least_populated_vds()

        self.assertIsNone(result)
```

- [ ] **Step 2: Run test to verify it fails**

```
make test ARGS="apps.vds.tests.test_models"
```
Expected: FAIL — `TypeError: VDSInstanceFactory() got an unexpected keyword argument 'is_keys_available'`

- [ ] **Step 3: Add field to `VDSInstance` and filter to `VDSQuerySet` in `src/apps/vds/models.py`**

Replace the `VDSQuerySet` class and the `is_keys_available` addition to `VDSInstance`:

```python
class VDSQuerySet(ActiveQuerySet):
    def order_by_population(self):
        return (
            self.active()
            .filter(is_keys_available=True)
            .annotate(keys_count_annotation=Count("keys"))
            .order_by("keys_count_annotation")
        )

    def get_least_populated(self):
        return self.order_by_population().first()
```

In `VDSInstance`, add after `user_limit`:

```python
is_keys_available = models.BooleanField("выпуск ключей доступен", default=True)
```

- [ ] **Step 4: Generate and apply migration**

```bash
cd src && python manage.py makemigrations vds --name vdsinstance_is_keys_available && python manage.py migrate
```
Expected: `Migrations for 'vds': src/apps/vds/migrations/0014_vdsinstance_is_keys_available.py`

- [ ] **Step 5: Run tests to verify they pass**

```
make test ARGS="apps.vds.tests.test_models"
```
Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/apps/vds/models.py \
        src/apps/vds/migrations/0014_vdsinstance_is_keys_available.py \
        src/apps/vds/tests/test_models.py
git commit -m "feat(vds): add is_keys_available to VDSInstance with QuerySet filter"
```

---

### Task 2: New `UpdateKeyOnAnotherVdsInfraService` (PATCH replication) + Celery task

Context: when a key is first issued, its secret is replicated to all other VDS servers via POST. On subsequent updates, those servers already have the user, so replication must use PATCH. This service is the PATCH counterpart to `AddKeyToAnotherVdsInfraService`.

**Files:**
- Create: `src/apps/vds/services/update_key_on_another_vds_infra_service.py`
- Modify: `src/apps/vds/tasks.py`
- Modify: `src/apps/vds/services/__init__.py`
- Create: `src/apps/vds/tests/test_services/test_update_key_on_another_vds_infra_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# src/apps/vds/tests/test_services/test_update_key_on_another_vds_infra_service.py
from __future__ import annotations

import json
from unittest.mock import patch

import responses
from django.test import TestCase

from apps.vds.services.update_key_on_another_vds_infra_service import (
    get_update_key_on_another_vds_instances_service,
)
from apps.vds.tests.factories import VDSInstanceFactory


class TestUpdateKeyOnAnotherVdsInfraService(TestCase):
    def setUp(self) -> None:
        self.excluded = VDSInstanceFactory()
        self.target_1 = VDSInstanceFactory()
        self.target_2 = VDSInstanceFactory()

    def _mock_targets(self) -> None:
        for server in (self.target_1, self.target_2):
            responses.add(
                method=responses.PATCH,
                url=f"{server.internal_url}/api/users",
                json={"status": "ok"},
            )

    @responses.activate
    def test_patches_all_instances_except_excluded(self) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.excluded.internal_url}/api/users",
            json={"status": "ok"},
        )
        self._mock_targets()

        get_update_key_on_another_vds_instances_service()(
            exclude=self.excluded.pk,
            username="John",
            secret="test_secret",
        )

        called_urls = [call.request.url for call in responses.calls]
        self.assertEqual(len(responses.calls), 2)
        self.assertNotIn(f"{self.excluded.internal_url}/api/users", called_urls)

    @responses.activate
    def test_uses_patch_http_method(self) -> None:
        self._mock_targets()

        get_update_key_on_another_vds_instances_service()(
            exclude=self.excluded.pk,
            username="John",
            secret="test_secret",
        )

        for call in responses.calls:
            self.assertEqual(call.request.method, "PATCH")

    @responses.activate
    def test_sends_correct_payload(self) -> None:
        self._mock_targets()

        get_update_key_on_another_vds_instances_service()(
            exclude=self.excluded.pk,
            username="John",
            secret="test_secret",
        )

        for call in responses.calls:
            body = json.loads(call.request.body)
            self.assertEqual(body["username"], "John")
            self.assertEqual(body["secret"], "test_secret")

    @responses.activate
    def test_continues_on_http_error_and_notifies_admin(self) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.target_1.internal_url}/api/users",
            status=500,
        )
        responses.add(
            method=responses.PATCH,
            url=f"{self.target_2.internal_url}/api/users",
            json={"status": "ok"},
        )

        with patch(
            "apps.vds.services.update_key_on_another_vds_infra_service.send_telegram_message"
        ) as mock_send:
            get_update_key_on_another_vds_instances_service()(
                exclude=self.excluded.pk,
                username="John",
                secret="test_secret",
            )

        self.assertEqual(len(responses.calls), 2)
        mock_send.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```
make test ARGS="apps.vds.tests.test_services.test_update_key_on_another_vds_infra_service"
```
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.vds.services.update_key_on_another_vds_infra_service'`

- [ ] **Step 3: Create `src/apps/vds/services/update_key_on_another_vds_infra_service.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

import requests
from django.conf import settings
from django.utils import html

from apps.core.telegram.transport import send_telegram_message
from apps.vds.selectors import get_other_active_vds_instances

if TYPE_CHECKING:
    from apps.vds.models import VDSInstance


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class UpdateKeyOnAnotherVdsInfraService:
    def __call__(self, *, exclude: int, username: str, secret: str) -> None:
        servers = get_other_active_vds_instances(exclude_pk=exclude)
        for server in servers:
            self._update_key_on_server(server=server, username=username, secret=secret)

    def _update_key_on_server(self, *, server: VDSInstance, username: str, secret: str) -> None:
        try:
            response = requests.patch(
                url=f"{server.internal_url}/api/users",
                json={"username": username, "secret": secret},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except Exception as exc:
            self._notify_admin(server=server, username=username, exc=exc)

    @staticmethod
    def _notify_admin(*, server: VDSInstance, username: str, exc: Exception) -> None:
        escaped_error = html.escape(str(exc))
        send_telegram_message(
            chat_id=int(settings.MY_TELEGRAM_ID),
            text=(
                "🔴 <b>(BACKEND) Системное оповещение</b>\n\n"
                "🛡 <b>Тип ошибки:</b> SERVER INTERNAL ERROR (500)\n"
                "📋 <b>Детали:</b>\n"
                f"- Не удалось обновить ключ на сервере\n"
                f"- Сервер — <b>{server.internal_url}</b>\n"
                f"- Порядковый номер сервера — <b>#{server.number}</b>\n"
                f"- Пользователь — <b>{username}</b>\n\n"
                f"<code>{escaped_error}</code>\n\n"
                "⚙️ <i>Требуется внимание команды!</i>"
            ),
        )


def get_update_key_on_another_vds_instances_service() -> UpdateKeyOnAnotherVdsInfraService:
    return UpdateKeyOnAnotherVdsInfraService()
```

- [ ] **Step 4: Add Celery task to `src/apps/vds/tasks.py`**

Add after `add_key_to_another_vds_instances_task`:

```python
@shared_task
def update_key_on_another_vds_instances_task(exclude: int, username: str, secret: str) -> None:
    from apps.vds.services import get_update_key_on_another_vds_instances_service

    get_update_key_on_another_vds_instances_service()(exclude=exclude, username=username, secret=secret)
```

- [ ] **Step 5: Export from `src/apps/vds/services/__init__.py`**

Add import block (before the `__all__` list):

```python
from apps.vds.services.update_key_on_another_vds_infra_service import (
    UpdateKeyOnAnotherVdsInfraService,
    get_update_key_on_another_vds_instances_service,
)
```

Add to `__all__`:

```python
"UpdateKeyOnAnotherVdsInfraService",
"get_update_key_on_another_vds_instances_service",
```

- [ ] **Step 6: Run tests to verify they pass**

```
make test ARGS="apps.vds.tests.test_services.test_update_key_on_another_vds_infra_service"
```
Expected: 4 tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/apps/vds/services/update_key_on_another_vds_infra_service.py \
        src/apps/vds/tasks.py \
        src/apps/vds/services/__init__.py \
        src/apps/vds/tests/test_services/test_update_key_on_another_vds_infra_service.py
git commit -m "feat(vds): add UpdateKeyOnAnotherVdsInfraService with PATCH replication"
```

---

### Task 3: Fix `UpdateKeyInfraService` — explicit `server` param + PATCH replication task

Context: `UpdateKeyInfraService` currently uses `old_key.vds` as the target server and dispatches the POST-based replication task — both are wrong for the update flow. This task fixes the signature to accept an explicit `server: VDSInstance` and switches replication to the PATCH task from Task 2. `UpdateKeyService` is updated minimally (passes `server=key.vds`) to keep it working while the migration logic is added in Task 4.

**Files:**
- Modify: `src/apps/vds/services/update_key_infra_service.py`
- Modify: `src/apps/vds/services/update_key_service.py` (one line change only)
- Create: `src/apps/vds/tests/test_services/test_update_key_infra_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# src/apps/vds/tests/test_services/test_update_key_infra_service.py
from __future__ import annotations

import json
from unittest import mock

import responses
from django.test import TestCase

from apps.vds.services import get_update_key_infra_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


@mock.patch("apps.notifications.services.send_notification_service.send_telegram_message")
@mock.patch("apps.core.decorators._log_infra_error")
class TestUpdateKeyInfraService(TestCase):
    def setUp(self) -> None:
        self.key = MTPRotoKeyFactory()
        self.server = self.key.vds

    @responses.activate
    @mock.patch("apps.vds.services.update_key_infra_service.update_key_on_another_vds_instances_task")
    def test_sends_patch_to_target_server(self, mock_task, mock_log, mock_send) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            json={"key": "new_token", "tls_domain": "new.domain"},
        )

        result = get_update_key_infra_service()(
            server=self.server,
            username=str(self.key.user.username),
        )

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.method, "PATCH")
        body = json.loads(responses.calls[0].request.body)
        self.assertEqual(body["username"], str(self.key.user.username))
        self.assertEqual(result.key, "new_token")
        self.assertEqual(result.tls_domain, "new.domain")

    @responses.activate
    @mock.patch("apps.vds.services.update_key_infra_service.update_key_on_another_vds_instances_task")
    def test_dispatches_patch_replication_task(self, mock_task, mock_log, mock_send) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            json={"key": "new_token", "tls_domain": "new.domain"},
        )

        get_update_key_infra_service()(
            server=self.server,
            username=str(self.key.user.username),
        )

        mock_task.delay.assert_called_once_with(
            exclude=self.server.pk,
            username=str(self.key.user.username),
            secret=mock.ANY,
        )

    @responses.activate
    @mock.patch("apps.vds.services.update_key_infra_service.update_key_on_another_vds_instances_task")
    def test_can_target_server_different_from_key_vds(self, mock_task, mock_log, mock_send) -> None:
        new_server = VDSInstanceFactory()
        responses.add(
            method=responses.PATCH,
            url=f"{new_server.internal_url}/api/users",
            json={"key": "new_token", "tls_domain": "new.domain"},
        )

        get_update_key_infra_service()(
            server=new_server,
            username=str(self.key.user.username),
        )

        self.assertEqual(
            responses.calls[0].request.url,
            f"{new_server.internal_url}/api/users",
        )
```

- [ ] **Step 2: Run test to verify it fails**

```
make test ARGS="apps.vds.tests.test_services.test_update_key_infra_service"
```
Expected: FAIL — `TypeError: UpdateKeyInfraService.__call__() got unexpected keyword argument 'server'`

- [ ] **Step 3: Rewrite `src/apps/vds/services/update_key_infra_service.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

import requests
from django.conf import settings

from apps.core.decorators import log_infra_error
from apps.vds.exceptions import VDSNotAvailable
from apps.vds.services.dtos import VDSKeyResponseOut
from apps.vds.tasks import update_key_on_another_vds_instances_task

if TYPE_CHECKING:
    from apps.vds.models import VDSInstance


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class UpdateKeyInfraService:
    @log_infra_error
    def __call__(self, *, server: VDSInstance, username: str) -> VDSKeyResponseOut | None:
        try:
            secret = str(os.urandom(16).hex())
            response = requests.patch(
                url=f"{server.internal_url}/api/users",
                json={"username": username, "secret": secret},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            update_key_on_another_vds_instances_task.delay(
                exclude=server.pk, username=username, secret=secret
            )
            return VDSKeyResponseOut(**response.json())
        except Exception as exc:
            raise VDSNotAvailable(
                method="update-user",
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


def get_update_key_infra_service() -> UpdateKeyInfraService:
    return UpdateKeyInfraService()
```

- [ ] **Step 4: Update call site in `src/apps/vds/services/update_key_service.py`**

Change only the `infra()` call (line 38). Replace:

```python
response = infra(username=username, old_key=key)
```

With:

```python
response = infra(username=username, server=key.vds)
```

- [ ] **Step 5: Run all tests**

```
make test
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/apps/vds/services/update_key_infra_service.py \
        src/apps/vds/services/update_key_service.py \
        src/apps/vds/tests/test_services/test_update_key_infra_service.py
git commit -m "fix(vds): UpdateKeyInfraService accepts explicit server and uses PATCH replication"
```

---

### Task 4: VDS selection and migration logic in `UpdateKeyService`

Context: currently `UpdateKeyService` always patches the key's existing VDS. After this task it will call `get_least_populated_vds()` (which already filters `is_keys_available=True` from Task 1) and update `key.vds` + `key.node_number` if the selected server differs from the current one — this is the migration path.

**Files:**
- Modify: `src/apps/vds/services/update_key_service.py`
- Create: `src/apps/vds/tests/test_services/test_update_key_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# src/apps/vds/tests/test_services/test_update_key_service.py
from __future__ import annotations

from datetime import timedelta
from unittest import mock

import responses
from django.test import TestCase
from django.utils import timezone

from apps.vds.services import get_update_key_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


@mock.patch("apps.notifications.services.send_notification_service.send_telegram_message")
@mock.patch("apps.core.decorators._log_infra_error")
class TestUpdateKeyServiceVDSSelection(TestCase):
    def setUp(self) -> None:
        self.future = timezone.now() + timedelta(days=30)

    @responses.activate
    @mock.patch("apps.vds.services.update_key_infra_service.update_key_on_another_vds_instances_task")
    def test_stays_on_same_vds_when_available(
        self, mock_task, mock_log, mock_send
    ) -> None:
        vds = VDSInstanceFactory(is_keys_available=True)
        key = MTPRotoKeyFactory(vds=vds, expired_date=self.future)
        responses.add(
            method=responses.PATCH,
            url=f"{vds.internal_url}/api/users",
            json={"key": "new_token", "tls_domain": "new.domain"},
        )

        get_update_key_service()(username=str(key.user.username))

        key.refresh_from_db()
        self.assertEqual(key.vds_id, vds.pk)
        self.assertEqual(key.node_number, vds.name)
        self.assertEqual(key.token, "new_token")

    @responses.activate
    @mock.patch("apps.vds.services.update_key_infra_service.update_key_on_another_vds_instances_task")
    def test_migrates_to_new_vds_when_current_has_keys_unavailable(
        self, mock_task, mock_log, mock_send
    ) -> None:
        old_vds = VDSInstanceFactory(is_keys_available=False)
        new_vds = VDSInstanceFactory(is_keys_available=True)
        key = MTPRotoKeyFactory(vds=old_vds, expired_date=self.future)
        responses.add(
            method=responses.PATCH,
            url=f"{new_vds.internal_url}/api/users",
            json={"key": "migrated_token", "tls_domain": "migrated.domain"},
        )

        get_update_key_service()(username=str(key.user.username))

        key.refresh_from_db()
        self.assertEqual(key.vds_id, new_vds.pk)
        self.assertEqual(key.node_number, new_vds.name)
        self.assertEqual(key.token, "migrated_token")
        self.assertEqual(key.tls_domain, "migrated.domain")

    @responses.activate
    @mock.patch("apps.vds.services.update_key_infra_service.update_key_on_another_vds_instances_task")
    def test_patch_is_sent_to_selected_vds_not_old_vds(
        self, mock_task, mock_log, mock_send
    ) -> None:
        old_vds = VDSInstanceFactory(is_keys_available=False)
        new_vds = VDSInstanceFactory(is_keys_available=True)
        key = MTPRotoKeyFactory(vds=old_vds, expired_date=self.future)
        responses.add(
            method=responses.PATCH,
            url=f"{new_vds.internal_url}/api/users",
            json={"key": "migrated_token", "tls_domain": "migrated.domain"},
        )

        get_update_key_service()(username=str(key.user.username))

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            f"{new_vds.internal_url}/api/users",
        )
```

- [ ] **Step 2: Run test to verify it fails**

```
make test ARGS="apps.vds.tests.test_services.test_update_key_service"
```
Expected: `test_migrates_to_new_vds_when_current_has_keys_unavailable` and `test_patch_is_sent_to_selected_vds_not_old_vds` FAIL — service still uses `key.vds` directly.

- [ ] **Step 3: Rewrite `src/apps/vds/services/update_key_service.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import final

from django.db import transaction
from django.utils import timezone

from apps.core.decorators import log_service_error
from apps.users.selectors import get_user_by_username
from apps.vds.exceptions import KeyDoesNotExist, TooManyRequests
from apps.vds.selectors import get_active_key, get_keys_by_username, get_least_populated_vds
from apps.vds.services import get_update_key_infra_service
from apps.vds.services.dtos import UpdateKeyOut


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class UpdateKeyService:
    @log_service_error
    def __call__(self, *, username: str) -> UpdateKeyOut | None:
        user = get_user_by_username(username=username)
        if user is None:
            raise KeyDoesNotExist(telegram_id=username)
        key = get_active_key(user=user)
        if key is None:
            raise KeyDoesNotExist(telegram_id=username)

        if key.last_update and (
            key.last_update + timedelta(minutes=5) > timezone.now()
        ):
            raise TooManyRequests(telegram_id=username)

        with transaction.atomic():
            server = get_least_populated_vds()
            infra = get_update_key_infra_service()
            response = infra(username=username, server=server)

            key.vds = server
            key.token = response.key
            key.tls_domain = response.tls_domain
            key.node_number = server.name
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

            get_keys_by_username(username=username).exclude(pk=key.pk).delete()

        return UpdateKeyOut(
            link=key.get_proxy_link(),
            expired_date=key.expired_date.date().strftime("%d.%m.%y"),
        )


def get_update_key_service() -> UpdateKeyService:
    return UpdateKeyService()
```

- [ ] **Step 4: Run all tests**

```
make test
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/apps/vds/services/update_key_service.py \
        src/apps/vds/tests/test_services/test_update_key_service.py
git commit -m "feat(vds): UpdateKeyService selects VDS by is_keys_available and migrates when needed"
```
