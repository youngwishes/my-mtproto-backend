# VDS Replication Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic retry + health-check recovery to VDS key replication so transient and extended server outages are handled without manual intervention.

**Architecture:** Per-server Celery tasks replace the current all-servers-in-one approach; each retries with exponential backoff (60s → 240s → 960s). On retry exhaustion the server is marked `is_healthy=False`. A periodic `check_vds_health_task` pings unhealthy servers every 5 minutes and triggers `sync_keys_to_vds_task` when they recover.

**Tech Stack:** Django ORM, Celery (`bind=True`, `max_retries`, `MaxRetriesExceededError`), `responses` library for HTTP mocking, `unittest.mock`.

---

## File Map

**New files:**
- `src/apps/vds/services/replicate_key_add_to_server_infra_service.py`
- `src/apps/vds/services/replicate_key_update_to_server_infra_service.py`
- `src/apps/vds/services/vds_health_check_infra_service.py`
- `src/apps/vds/tests/test_services/test_replicate_key_add_to_server_infra_service.py`
- `src/apps/vds/tests/test_services/test_replicate_key_update_to_server_infra_service.py`
- `src/apps/vds/tests/test_services/test_vds_health_check_infra_service.py`
- `src/apps/vds/tests/test_tasks/test_replicate_key_tasks.py`
- `src/apps/vds/tests/test_tasks/test_check_vds_health_task.py`

**Modified files:**
- `src/apps/vds/models.py` — add `is_healthy` field
- `src/apps/vds/selectors.py` — add `get_unhealthy_vds_instances()`
- `src/apps/vds/tasks.py` — add `_handle_replication_failure`, new tasks, refactor dispatch tasks
- `src/apps/vds/services/__init__.py` — remove old exports, add new ones
- `src/apps/vds/admin.py` — add `is_healthy` to `VDSInstanceAdmin`
- `src/config/settings/celery.py` — add `check-vds-health` to beat schedule

**Deleted files:**
- `src/apps/vds/services/add_key_to_another_vds_infra_service.py`
- `src/apps/vds/services/update_key_on_another_vds_infra_service.py`
- `src/apps/vds/tests/test_services/test_add_key_to_another_vds_infra_service.py`
- `src/apps/vds/tests/test_services/test_update_key_on_another_vds_infra_service.py`

---

## Task 1: Add `is_healthy` to `VDSInstance` and selector

**Files:**
- Modify: `src/apps/vds/models.py`
- Modify: `src/apps/vds/selectors.py`
- Test: `src/apps/vds/tests/test_selectors.py`

- [ ] **Step 1: Write the failing test for `get_unhealthy_vds_instances`**

Open `src/apps/vds/tests/test_selectors.py` and add at the bottom:

```python
from apps.vds.selectors import get_unhealthy_vds_instances

class TestGetUnhealthyVdsInstances(TestCase):
    def test_returns_only_active_unhealthy_instances(self) -> None:
        healthy = VDSInstanceFactory(is_healthy=True)
        unhealthy = VDSInstanceFactory(is_healthy=False)
        inactive_unhealthy = VDSInstanceFactory(is_active=False, is_healthy=False)

        result = list(get_unhealthy_vds_instances())

        self.assertNotIn(healthy, result)
        self.assertIn(unhealthy, result)
        self.assertNotIn(inactive_unhealthy, result)
```

Note: `VDSInstanceFactory` already creates instances with `is_active=True` by default (inherited from `BaseDjangoModel`). The `is_healthy` field doesn't exist yet — the test will fail with a `TypeError` on factory creation.

- [ ] **Step 2: Run the test to confirm it fails**

```
make test ARGS="apps.vds.tests.test_selectors.TestGetUnhealthyVdsInstances"
```

Expected: `TypeError` or `FieldError` — `is_healthy` does not exist on the model.

- [ ] **Step 3: Add `is_healthy` field to `VDSInstance`**

In `src/apps/vds/models.py`, add after `is_keys_available`:

```python
is_healthy = models.BooleanField("сервер здоров", default=True)
```

Full updated field list in `VDSInstance`:
```python
name = models.CharField("название сервера")
number = models.PositiveSmallIntegerField("порядковый номер", unique=True)
ip_address = models.CharField("IP-адрес", unique=True)
internal_ip_address = models.CharField("внутренний IP-адрес", blank=True)
port = models.SmallIntegerField("порт", default=8000)
user_limit = models.PositiveSmallIntegerField("лимит пользователей", default=200)
is_keys_available = models.BooleanField("выпуск ключей доступен", default=True)
is_healthy = models.BooleanField("сервер здоров", default=True)
location = models.CharField("геолокация", default="", blank=True)
```

- [ ] **Step 4: Generate and apply migration**

```bash
cd src && python manage.py makemigrations vds --name="vdsinstance_is_healthy"
cd src && python manage.py migrate
```

- [ ] **Step 5: Add `get_unhealthy_vds_instances` to selectors**

In `src/apps/vds/selectors.py`, add at the bottom:

```python
def get_unhealthy_vds_instances() -> QuerySet[VDSInstance]:
    """Активные VDS-серверы, помеченные как нездоровые."""
    return VDSInstance.objects.active().filter(is_healthy=False)
```

- [ ] **Step 6: Run the test — confirm it passes**

```
make test ARGS="apps.vds.tests.test_selectors.TestGetUnhealthyVdsInstances"
```

Expected: PASS

- [ ] **Step 7: Run all existing tests to confirm no regressions**

```
make test
```

Expected: all green (new field has `default=True`, so existing data and factories are unaffected).

- [ ] **Step 8: Commit**

```bash
git add src/apps/vds/models.py src/apps/vds/selectors.py src/apps/vds/migrations/ src/apps/vds/tests/test_selectors.py
git commit -m "feat(vds): add is_healthy field to VDSInstance and unhealthy selector"
```

---

## Task 2: Update `VDSInstanceAdmin`

**Files:**
- Modify: `src/apps/vds/admin.py`

- [ ] **Step 1: Add `is_healthy` to admin display and editable**

In `src/apps/vds/admin.py`, update `VDSInstanceAdmin`:

```python
@admin.register(VDSInstance)
class VDSInstanceAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "name",
        "internal_ip_address",
        "number",
        "active_keys_count",
        "not_active_keys_count",
        "user_limit",
        "is_active",
        "is_healthy",
    ]
    list_editable = ["is_active", "is_healthy"]
    actions = (migrate_vds_keys, remove_expired_keys, remove_dead_keys, sync_keys_to_vds)
```

- [ ] **Step 2: Commit**

```bash
git add src/apps/vds/admin.py
git commit -m "feat(vds): show is_healthy in VDSInstance admin"
```

---

## Task 3: `ReplicateKeyAddToServerInfraService`

**Files:**
- Create: `src/apps/vds/services/replicate_key_add_to_server_infra_service.py`
- Create: `src/apps/vds/tests/test_services/test_replicate_key_add_to_server_infra_service.py`

- [ ] **Step 1: Write the failing tests**

Create `src/apps/vds/tests/test_services/test_replicate_key_add_to_server_infra_service.py`:

```python
from __future__ import annotations

import json

import responses
from django.test import TestCase

from apps.vds.tests.factories import VDSInstanceFactory


class TestReplicateKeyAddToServerInfraService(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory()

    def _get_service(self):
        from apps.vds.services.replicate_key_add_to_server_infra_service import (
            get_replicate_key_add_to_server_infra_service,
        )
        return get_replicate_key_add_to_server_infra_service()

    @responses.activate
    def test_posts_to_server_with_correct_payload(self) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        self._get_service()(server_id=self.server.pk, username="john", secret="abc123")

        self.assertEqual(len(responses.calls), 1)
        body = json.loads(responses.calls[0].request.body)
        self.assertEqual(body["username"], "john")
        self.assertEqual(body["secret"], "abc123")
        self.assertEqual(responses.calls[0].request.method, "POST")

    @responses.activate
    def test_returns_silently_on_409(self) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.server.internal_url}/api/users",
            status=409,
            json={"detail": "already exists"},
        )

        # Should not raise
        self._get_service()(server_id=self.server.pk, username="john", secret="abc123")
        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_raises_on_server_error(self) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.server.internal_url}/api/users",
            status=500,
            json={"error": "internal server error"},
        )

        with self.assertRaises(Exception):
            self._get_service()(server_id=self.server.pk, username="john", secret="abc123")

    @responses.activate
    def test_raises_on_connection_error(self) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.server.internal_url}/api/users",
            body=ConnectionError("Connection refused"),
        )

        with self.assertRaises(Exception):
            self._get_service()(server_id=self.server.pk, username="john", secret="abc123")
```

- [ ] **Step 2: Run to confirm failure**

```
make test ARGS="apps.vds.tests.test_services.test_replicate_key_add_to_server_infra_service"
```

Expected: `ImportError` — module does not exist yet.

- [ ] **Step 3: Implement the service**

Create `src/apps/vds/services/replicate_key_add_to_server_infra_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import final

import requests
from django.conf import settings

from apps.vds.selectors import get_vds_instance_by_id


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReplicateKeyAddToServerInfraService:
    def __call__(self, *, server_id: int, username: str, secret: str) -> None:
        server = get_vds_instance_by_id(pk=server_id)
        response = requests.post(
            url=f"{server.internal_url}/api/users",
            json={"username": username, "secret": secret},
            timeout=settings.VDS_REQUEST_TIMEOUT,
        )
        if response.status_code == 409:
            return
        response.raise_for_status()


def get_replicate_key_add_to_server_infra_service() -> ReplicateKeyAddToServerInfraService:
    return ReplicateKeyAddToServerInfraService()
```

- [ ] **Step 4: Run tests — confirm they pass**

```
make test ARGS="apps.vds.tests.test_services.test_replicate_key_add_to_server_infra_service"
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/apps/vds/services/replicate_key_add_to_server_infra_service.py \
        src/apps/vds/tests/test_services/test_replicate_key_add_to_server_infra_service.py
git commit -m "feat(vds): add ReplicateKeyAddToServerInfraService with TDD"
```

---

## Task 4: `ReplicateKeyUpdateToServerInfraService`

**Files:**
- Create: `src/apps/vds/services/replicate_key_update_to_server_infra_service.py`
- Create: `src/apps/vds/tests/test_services/test_replicate_key_update_to_server_infra_service.py`

- [ ] **Step 1: Write the failing tests**

Create `src/apps/vds/tests/test_services/test_replicate_key_update_to_server_infra_service.py`:

```python
from __future__ import annotations

import json

import responses
from django.test import TestCase

from apps.vds.tests.factories import VDSInstanceFactory


class TestReplicateKeyUpdateToServerInfraService(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory()

    def _get_service(self):
        from apps.vds.services.replicate_key_update_to_server_infra_service import (
            get_replicate_key_update_to_server_infra_service,
        )
        return get_replicate_key_update_to_server_infra_service()

    @responses.activate
    def test_patches_server_with_correct_payload(self) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        self._get_service()(server_id=self.server.pk, username="john", secret="abc123")

        self.assertEqual(len(responses.calls), 1)
        body = json.loads(responses.calls[0].request.body)
        self.assertEqual(body["username"], "john")
        self.assertEqual(body["secret"], "abc123")
        self.assertEqual(responses.calls[0].request.method, "PATCH")

    @responses.activate
    def test_falls_back_to_post_on_404(self) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            status=404,
            json={"detail": "not found"},
        )
        responses.add(
            method=responses.POST,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        self._get_service()(server_id=self.server.pk, username="john", secret="abc123")

        self.assertEqual(len(responses.calls), 2)
        self.assertEqual(responses.calls[0].request.method, "PATCH")
        self.assertEqual(responses.calls[1].request.method, "POST")
        post_body = json.loads(responses.calls[1].request.body)
        self.assertEqual(post_body["secret"], "abc123")

    @responses.activate
    def test_raises_on_server_error(self) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            status=500,
        )

        with self.assertRaises(Exception):
            self._get_service()(server_id=self.server.pk, username="john", secret="abc123")

    @responses.activate
    def test_raises_on_connection_error(self) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            body=ConnectionError("Connection refused"),
        )

        with self.assertRaises(Exception):
            self._get_service()(server_id=self.server.pk, username="john", secret="abc123")
```

- [ ] **Step 2: Run to confirm failure**

```
make test ARGS="apps.vds.tests.test_services.test_replicate_key_update_to_server_infra_service"
```

Expected: `ImportError`.

- [ ] **Step 3: Implement the service**

Create `src/apps/vds/services/replicate_key_update_to_server_infra_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import final

import requests
from django.conf import settings

from apps.vds.selectors import get_vds_instance_by_id


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReplicateKeyUpdateToServerInfraService:
    def __call__(self, *, server_id: int, username: str, secret: str) -> None:
        server = get_vds_instance_by_id(pk=server_id)
        response = requests.patch(
            url=f"{server.internal_url}/api/users",
            json={"username": username, "secret": secret},
            timeout=settings.VDS_REQUEST_TIMEOUT,
        )
        if response.status_code == 404:
            response = requests.post(
                url=f"{server.internal_url}/api/users",
                json={"username": username, "secret": secret},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
        response.raise_for_status()


def get_replicate_key_update_to_server_infra_service() -> ReplicateKeyUpdateToServerInfraService:
    return ReplicateKeyUpdateToServerInfraService()
```

- [ ] **Step 4: Run tests — confirm they pass**

```
make test ARGS="apps.vds.tests.test_services.test_replicate_key_update_to_server_infra_service"
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/apps/vds/services/replicate_key_update_to_server_infra_service.py \
        src/apps/vds/tests/test_services/test_replicate_key_update_to_server_infra_service.py
git commit -m "feat(vds): add ReplicateKeyUpdateToServerInfraService with TDD"
```

---

## Task 5: `VDSHealthCheckInfraService`

**Files:**
- Create: `src/apps/vds/services/vds_health_check_infra_service.py`
- Create: `src/apps/vds/tests/test_services/test_vds_health_check_infra_service.py`

- [ ] **Step 1: Write the failing tests**

Create `src/apps/vds/tests/test_services/test_vds_health_check_infra_service.py`:

```python
from __future__ import annotations

import responses
from django.test import TestCase

from apps.vds.tests.factories import VDSInstanceFactory


class TestVdsHealthCheckInfraService(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory()

    def _get_service(self):
        from apps.vds.services.vds_health_check_infra_service import (
            get_vds_health_check_infra_service,
        )
        return get_vds_health_check_infra_service()

    @responses.activate
    def test_returns_true_when_server_responds(self) -> None:
        responses.add(
            method=responses.GET,
            url=self.server.internal_url,
            json={"status": "ok"},
        )

        result = self._get_service()(instance_id=self.server.pk)

        self.assertTrue(result)

    @responses.activate
    def test_returns_true_even_on_404_response(self) -> None:
        responses.add(
            method=responses.GET,
            url=self.server.internal_url,
            status=404,
        )

        result = self._get_service()(instance_id=self.server.pk)

        self.assertTrue(result)

    @responses.activate
    def test_returns_false_on_connection_error(self) -> None:
        responses.add(
            method=responses.GET,
            url=self.server.internal_url,
            body=ConnectionError("Connection refused"),
        )

        result = self._get_service()(instance_id=self.server.pk)

        self.assertFalse(result)
```

- [ ] **Step 2: Run to confirm failure**

```
make test ARGS="apps.vds.tests.test_services.test_vds_health_check_infra_service"
```

Expected: `ImportError`.

- [ ] **Step 3: Implement the service**

Create `src/apps/vds/services/vds_health_check_infra_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import final

import requests

from apps.vds.selectors import get_vds_instance_by_id

_HEALTH_CHECK_TIMEOUT = 5


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VDSHealthCheckInfraService:
    def __call__(self, *, instance_id: int) -> bool:
        server = get_vds_instance_by_id(pk=instance_id)
        try:
            requests.get(url=server.internal_url, timeout=_HEALTH_CHECK_TIMEOUT)
            return True
        except Exception:
            return False


def get_vds_health_check_infra_service() -> VDSHealthCheckInfraService:
    return VDSHealthCheckInfraService()
```

- [ ] **Step 4: Run tests — confirm they pass**

```
make test ARGS="apps.vds.tests.test_services.test_vds_health_check_infra_service"
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/apps/vds/services/vds_health_check_infra_service.py \
        src/apps/vds/tests/test_services/test_vds_health_check_infra_service.py
git commit -m "feat(vds): add VDSHealthCheckInfraService with TDD"
```

---

## Task 6: `_handle_replication_failure` + retry tasks

**Files:**
- Modify: `src/apps/vds/tasks.py`
- Create: `src/apps/vds/tests/test_tasks/test_replicate_key_tasks.py`

- [ ] **Step 1: Write the failing tests**

Create `src/apps/vds/tests/test_tasks/test_replicate_key_tasks.py`:

```python
from __future__ import annotations

from unittest.mock import patch

import responses
from django.test import TestCase

from apps.vds.tasks import _handle_replication_failure
from apps.vds.tests.factories import VDSInstanceFactory


class TestHandleReplicationFailure(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory(is_healthy=True)

    @patch("apps.core.telegram.transport.send_telegram_message")
    def test_marks_server_as_unhealthy(self, mock_send) -> None:
        _handle_replication_failure(
            server_id=self.server.pk,
            username="john",
            exc=Exception("Connection refused"),
        )

        self.server.refresh_from_db()
        self.assertFalse(self.server.is_healthy)

    @patch("apps.core.telegram.transport.send_telegram_message")
    def test_sends_admin_notification(self, mock_send) -> None:
        _handle_replication_failure(
            server_id=self.server.pk,
            username="john",
            exc=Exception("Connection refused"),
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        self.assertIn("john", str(call_kwargs))

    @patch("apps.core.telegram.transport.send_telegram_message")
    def test_does_not_crash_when_server_not_found(self, mock_send) -> None:
        # Should not raise even if server_id is invalid
        _handle_replication_failure(
            server_id=99999,
            username="john",
            exc=Exception("boom"),
        )
        mock_send.assert_called_once()


class TestReplicateKeyAddToServerTask(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory()

    @responses.activate
    def test_calls_service_on_success(self) -> None:
        from apps.vds.tasks import replicate_key_add_to_server_task

        responses.add(
            method=responses.POST,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        replicate_key_add_to_server_task.apply(
            args=[self.server.pk, "john", "abc123"]
        )

        self.assertEqual(len(responses.calls), 1)

    @patch("apps.vds.tasks._handle_replication_failure")
    def test_calls_handle_when_retries_exhausted(self, mock_handle) -> None:
        from apps.vds.tasks import replicate_key_add_to_server_task

        with patch(
            "apps.vds.services.replicate_key_add_to_server_infra_service."
            "get_replicate_key_add_to_server_infra_service"
        ) as mock_factory:
            mock_factory.return_value.side_effect = Exception("Connection refused")
            # retries=3 means we are already at max_retries — next retry raises MaxRetriesExceededError
            replicate_key_add_to_server_task.apply(
                args=[self.server.pk, "john", "abc123"],
                retries=3,
            )

        mock_handle.assert_called_once_with(
            server_id=self.server.pk,
            username="john",
            exc=mock_handle.call_args.kwargs["exc"],
        )


class TestReplicateKeyUpdateToServerTask(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory()

    @responses.activate
    def test_calls_service_on_success(self) -> None:
        from apps.vds.tasks import replicate_key_update_to_server_task

        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        replicate_key_update_to_server_task.apply(
            args=[self.server.pk, "john", "abc123"]
        )

        self.assertEqual(len(responses.calls), 1)

    @patch("apps.vds.tasks._handle_replication_failure")
    def test_calls_handle_when_retries_exhausted(self, mock_handle) -> None:
        from apps.vds.tasks import replicate_key_update_to_server_task

        with patch(
            "apps.vds.services.replicate_key_update_to_server_infra_service."
            "get_replicate_key_update_to_server_infra_service"
        ) as mock_factory:
            mock_factory.return_value.side_effect = Exception("Connection refused")
            replicate_key_update_to_server_task.apply(
                args=[self.server.pk, "john", "abc123"],
                retries=3,
            )

        mock_handle.assert_called_once()
```

- [ ] **Step 2: Run to confirm failure**

```
make test ARGS="apps.vds.tests.test_tasks.test_replicate_key_tasks"
```

Expected: `ImportError` — `_handle_replication_failure` and new tasks don't exist yet.

- [ ] **Step 3: Add `_handle_replication_failure` and new tasks to `tasks.py`**

Replace the full content of `src/apps/vds/tasks.py` with:

```python
from __future__ import annotations

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError


def _handle_replication_failure(*, server_id: int, username: str, exc: Exception) -> None:
    """Вызывается когда все ретраи репликации на сервер исчерпаны."""
    from apps.core.telegram.transport import send_telegram_message
    from django.conf import settings
    from django.utils import html

    from apps.vds.models import VDSInstance

    VDSInstance.objects.filter(pk=server_id).update(is_healthy=False)

    try:
        server = VDSInstance.objects.get(pk=server_id)
        server_info = f"#{server.number} ({server.internal_url})"
    except VDSInstance.DoesNotExist:
        server_info = f"ID={server_id}"

    escaped_error = html.escape(str(exc))
    send_telegram_message(
        chat_id=int(settings.MY_TELEGRAM_ID),
        text=(
            "🔴 <b>(BACKEND) Системное оповещение</b>\n\n"
            "🛡 <b>Тип ошибки:</b> REPLICATION FAILED (все ретраи исчерпаны)\n"
            "📋 <b>Детали:</b>\n"
            f"- Сервер — <b>{server_info}</b>\n"
            f"- Пользователь — <b>{username}</b>\n\n"
            f"<code>{escaped_error}</code>\n\n"
            "⚙️ <i>Сервер помечен как нездоровый. Health-check восстановит его автоматически.</i>"
        ),
    )


@shared_task
def migrate_vds_keys_task(from_instance_id: int) -> None:
    from apps.vds.services import get_migrate_vds_keys_service

    get_migrate_vds_keys_service()(from_instance_id=from_instance_id)


@shared_task
def remove_user_keys_daily():
    from apps.vds.services import get_remove_expired_keys_daily_service

    get_remove_expired_keys_daily_service()()


@shared_task
def remove_dead_keys_from_vds_task(instance_id: int) -> None:
    from apps.vds.services.remove_dead_keys_from_vds_infra_service import get_remove_dead_keys_from_vds_infra_service

    get_remove_dead_keys_from_vds_infra_service()(instance_id=instance_id)


@shared_task
def add_key_to_another_vds_instances_task(exclude: int, username: str, secret: str) -> None:
    from apps.vds.selectors import get_other_active_vds_instances

    for server in get_other_active_vds_instances(exclude_pk=exclude):
        replicate_key_add_to_server_task.delay(server.pk, username, secret)


@shared_task(bind=True, max_retries=3)
def replicate_key_add_to_server_task(self, server_id: int, username: str, secret: str) -> None:
    from apps.vds.services.replicate_key_add_to_server_infra_service import (
        get_replicate_key_add_to_server_infra_service,
    )

    try:
        get_replicate_key_add_to_server_infra_service()(
            server_id=server_id, username=username, secret=secret
        )
    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=60 * (4 ** self.request.retries))
        except MaxRetriesExceededError:
            _handle_replication_failure(server_id=server_id, username=username, exc=exc)


@shared_task
def update_key_on_another_vds_instances_task(exclude: int, username: str, secret: str) -> None:
    from apps.vds.selectors import get_other_active_vds_instances

    for server in get_other_active_vds_instances(exclude_pk=exclude):
        replicate_key_update_to_server_task.delay(server.pk, username, secret)


@shared_task(bind=True, max_retries=3)
def replicate_key_update_to_server_task(self, server_id: int, username: str, secret: str) -> None:
    from apps.vds.services.replicate_key_update_to_server_infra_service import (
        get_replicate_key_update_to_server_infra_service,
    )

    try:
        get_replicate_key_update_to_server_infra_service()(
            server_id=server_id, username=username, secret=secret
        )
    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=60 * (4 ** self.request.retries))
        except MaxRetriesExceededError:
            _handle_replication_failure(server_id=server_id, username=username, exc=exc)


@shared_task
def remove_key_from_another_vds_instances_task(server: int, keys_id: list[int]) -> None:
    from apps.vds.services import get_remove_keys_from_vds_instance_infra_service

    get_remove_keys_from_vds_instance_infra_service()(server_id=server, keys_ids=keys_id)


@shared_task
def sync_keys_to_vds_task(instance_id: int) -> None:
    from apps.vds.services import get_sync_keys_to_vds_infra_service

    get_sync_keys_to_vds_infra_service()(instance_id=instance_id)


@shared_task
def check_vds_health_task() -> None:
    from apps.vds.selectors import get_unhealthy_vds_instances
    from apps.vds.services.vds_health_check_infra_service import get_vds_health_check_infra_service

    service = get_vds_health_check_infra_service()
    for server in get_unhealthy_vds_instances():
        if service(instance_id=server.pk):
            server.is_healthy = True
            server.save(update_fields=["is_healthy"])
            sync_keys_to_vds_task.delay(instance_id=server.pk)
```

- [ ] **Step 4: Run the new task tests — confirm they pass**

```
make test ARGS="apps.vds.tests.test_tasks.test_replicate_key_tasks"
```

Expected: PASS

- [ ] **Step 5: Run all tests to confirm no regressions**

```
make test
```

Expected: all green. The existing test for `add_key_to_another_vds_instances_task` in `test_add_user_service.py` mocks the task via `add_key_to_another_vds_instances_task` — still works because the task signature hasn't changed.

- [ ] **Step 6: Commit**

```bash
git add src/apps/vds/tasks.py src/apps/vds/tests/test_tasks/test_replicate_key_tasks.py
git commit -m "feat(vds): add retry tasks and _handle_replication_failure"
```

---

## Task 7: `check_vds_health_task` tests

**Files:**
- Create: `src/apps/vds/tests/test_tasks/test_check_vds_health_task.py`

- [ ] **Step 1: Write the failing tests**

Create `src/apps/vds/tests/test_tasks/test_check_vds_health_task.py`:

```python
from __future__ import annotations

from unittest.mock import patch, call

from django.test import TestCase

from apps.vds.tasks import check_vds_health_task
from apps.vds.tests.factories import VDSInstanceFactory


class TestCheckVdsHealthTask(TestCase):
    def setUp(self) -> None:
        self.healthy_server = VDSInstanceFactory(is_healthy=True)
        self.unhealthy_server = VDSInstanceFactory(is_healthy=False)

    @patch("apps.vds.tasks.sync_keys_to_vds_task")
    @patch(
        "apps.vds.services.vds_health_check_infra_service."
        "get_vds_health_check_infra_service"
    )
    def test_recovers_server_and_triggers_sync(self, mock_service_factory, mock_sync) -> None:
        mock_service_factory.return_value.return_value = True

        check_vds_health_task()

        self.unhealthy_server.refresh_from_db()
        self.assertTrue(self.unhealthy_server.is_healthy)
        mock_sync.delay.assert_called_once_with(instance_id=self.unhealthy_server.pk)

    @patch("apps.vds.tasks.sync_keys_to_vds_task")
    @patch(
        "apps.vds.services.vds_health_check_infra_service."
        "get_vds_health_check_infra_service"
    )
    def test_skips_still_unreachable_server(self, mock_service_factory, mock_sync) -> None:
        mock_service_factory.return_value.return_value = False

        check_vds_health_task()

        self.unhealthy_server.refresh_from_db()
        self.assertFalse(self.unhealthy_server.is_healthy)
        mock_sync.delay.assert_not_called()

    @patch("apps.vds.tasks.sync_keys_to_vds_task")
    @patch(
        "apps.vds.services.vds_health_check_infra_service."
        "get_vds_health_check_infra_service"
    )
    def test_does_not_check_already_healthy_servers(self, mock_service_factory, mock_sync) -> None:
        mock_service_factory.return_value.return_value = True

        check_vds_health_task()

        # sync.delay called exactly once — only for unhealthy_server, not healthy_server
        mock_sync.delay.assert_called_once_with(instance_id=self.unhealthy_server.pk)

    @patch("apps.vds.tasks.sync_keys_to_vds_task")
    @patch(
        "apps.vds.services.vds_health_check_infra_service."
        "get_vds_health_check_infra_service"
    )
    def test_handles_multiple_unhealthy_servers(self, mock_service_factory, mock_sync) -> None:
        second_unhealthy = VDSInstanceFactory(is_healthy=False)
        mock_service_factory.return_value.return_value = True

        check_vds_health_task()

        self.assertEqual(mock_sync.delay.call_count, 2)
        called_ids = {c.kwargs["instance_id"] for c in mock_sync.delay.call_args_list}
        self.assertIn(self.unhealthy_server.pk, called_ids)
        self.assertIn(second_unhealthy.pk, called_ids)
```

- [ ] **Step 2: Run the tests — confirm they pass**

```
make test ARGS="apps.vds.tests.test_tasks.test_check_vds_health_task"
```

Expected: PASS (the task is already implemented in `tasks.py` from Task 6).

- [ ] **Step 3: Commit**

```bash
git add src/apps/vds/tests/test_tasks/test_check_vds_health_task.py
git commit -m "test(vds): add tests for check_vds_health_task"
```

---

## Task 8: Add `check_vds_health_task` to Celery Beat

**Files:**
- Modify: `src/config/settings/celery.py`

- [ ] **Step 1: Add the periodic schedule**

In `src/config/settings/celery.py`, add to `CELERY_BEAT_SCHEDULE`:

```python
from celery.schedules import crontab

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
)

CELERY_BEAT_SCHEDULE = {
    "remove_user_keys_daily": {
        "task": "apps.vds.tasks.remove_user_keys_daily",
        "schedule": crontab(hour=9, minute=0),
    },
    "notify_before_removing_daily": {
        "task": "apps.notifications.tasks.notify_before_removing_daily",
        "schedule": crontab(hour=15, minute=0),
    },
    "notify_before_removing_daily_hour_before": {
        "task": "apps.notifications.tasks.notify_before_removing_daily_hour_before",
        "schedule": crontab(hour=8, minute=0),
    },
    "check-vds-health": {
        "task": "apps.vds.tasks.check_vds_health_task",
        "schedule": crontab(minute="*/5"),
    },
}
```

- [ ] **Step 2: Commit**

```bash
git add src/config/settings/celery.py
git commit -m "feat(vds): schedule check_vds_health_task every 5 minutes"
```

---

## Task 9: Delete old services and update `__init__.py`

**Files:**
- Delete: `src/apps/vds/services/add_key_to_another_vds_infra_service.py`
- Delete: `src/apps/vds/services/update_key_on_another_vds_infra_service.py`
- Delete: `src/apps/vds/tests/test_services/test_add_key_to_another_vds_infra_service.py`
- Delete: `src/apps/vds/tests/test_services/test_update_key_on_another_vds_infra_service.py`
- Modify: `src/apps/vds/services/__init__.py`

- [ ] **Step 1: Delete the old service files and their tests**

```bash
rm src/apps/vds/services/add_key_to_another_vds_infra_service.py
rm src/apps/vds/services/update_key_on_another_vds_infra_service.py
rm src/apps/vds/tests/test_services/test_add_key_to_another_vds_infra_service.py
rm src/apps/vds/tests/test_services/test_update_key_on_another_vds_infra_service.py
```

- [ ] **Step 2: Update `services/__init__.py`**

Replace the full content of `src/apps/vds/services/__init__.py` with:

```python
from __future__ import annotations

from apps.vds.services.add_new_key_infra_service import (
    AddNewKeyInfraService,
    get_add_new_key_service_factory,
)
from apps.vds.services.migrate_keys_infra_service import (
    MigrateVdsKeysInfraService,
    get_migrate_vds_keys_service,
)
from apps.vds.services.issue_key_service import (
    IssueKeyService,
    get_issue_key_service,
)
from apps.vds.services.remove_expired_keys_daily_service import (
    RemoveExpiredKeysDailyService,
    get_remove_expired_keys_daily_service,
)
from apps.vds.services.remove_key_infra_service import (
    RemoveUserKeyInfraService,
    get_remove_user_key_infra_service,
)
from apps.vds.services.update_key_infra_service import (
    UpdateKeyInfraService,
    get_update_key_infra_service,
)
from apps.vds.services.remove_keys_from_vds_instance_infra_service import (
    RemoveKeysFromVdsInstanceInfraService,
    get_remove_keys_from_vds_instance_infra_service,
)
from apps.vds.services.update_key_service import (
    UpdateKeyService,
    get_update_key_service,
)
from apps.vds.services.remove_dead_keys_from_vds_infra_service import (
    RemoveDeadKeysFromVdsInfraService,
    get_remove_dead_keys_from_vds_infra_service,
)
from apps.vds.services.get_my_servers_service import (
    GetMyServersService,
    get_my_servers_service,
)
from apps.vds.services.sync_keys_to_vds_infra_service import (
    SyncKeysToVdsInfraService,
    get_sync_keys_to_vds_infra_service,
)
from apps.vds.services.replicate_key_add_to_server_infra_service import (
    ReplicateKeyAddToServerInfraService,
    get_replicate_key_add_to_server_infra_service,
)
from apps.vds.services.replicate_key_update_to_server_infra_service import (
    ReplicateKeyUpdateToServerInfraService,
    get_replicate_key_update_to_server_infra_service,
)
from apps.vds.services.vds_health_check_infra_service import (
    VDSHealthCheckInfraService,
    get_vds_health_check_infra_service,
)

__all__ = [
    "AddNewKeyInfraService",
    "get_add_new_key_service_factory",
    "MigrateVdsKeysInfraService",
    "get_migrate_vds_keys_service",
    "IssueKeyService",
    "get_issue_key_service",
    "RemoveExpiredKeysDailyService",
    "get_remove_expired_keys_daily_service",
    "RemoveUserKeyInfraService",
    "get_remove_user_key_infra_service",
    "UpdateKeyInfraService",
    "get_update_key_infra_service",
    "RemoveKeysFromVdsInstanceInfraService",
    "get_remove_keys_from_vds_instance_infra_service",
    "UpdateKeyService",
    "get_update_key_service",
    "RemoveDeadKeysFromVdsInfraService",
    "get_remove_dead_keys_from_vds_infra_service",
    "GetMyServersService",
    "get_my_servers_service",
    "SyncKeysToVdsInfraService",
    "get_sync_keys_to_vds_infra_service",
    "ReplicateKeyAddToServerInfraService",
    "get_replicate_key_add_to_server_infra_service",
    "ReplicateKeyUpdateToServerInfraService",
    "get_replicate_key_update_to_server_infra_service",
    "VDSHealthCheckInfraService",
    "get_vds_health_check_infra_service",
]
```

- [ ] **Step 3: Run the full test suite**

```
make test
```

Expected: all green. If any test imports the deleted services by name, fix that import to use the new services.

- [ ] **Step 4: Commit**

```bash
git add -u  # stages deletions and modifications
git add src/apps/vds/services/__init__.py
git commit -m "refactor(vds): remove old replication services, wire up new ones"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Covered by |
|---|---|
| `is_healthy` field on `VDSInstance` | Task 1 |
| `get_unhealthy_vds_instances` selector | Task 1 |
| `is_healthy` in admin | Task 2 |
| `ReplicateKeyAddToServerInfraService` | Task 3 |
| `ReplicateKeyUpdateToServerInfraService` | Task 4 |
| `VDSHealthCheckInfraService` | Task 5 |
| `_handle_replication_failure` (mark unhealthy + notify) | Task 6 |
| `replicate_key_add_to_server_task` (bind, max_retries=3) | Task 6 |
| `replicate_key_update_to_server_task` (bind, max_retries=3) | Task 6 |
| `add_key_to_another_vds_instances_task` refactored | Task 6 |
| `update_key_on_another_vds_instances_task` refactored | Task 6 |
| `check_vds_health_task` logic + tests | Tasks 6, 7 |
| Celery Beat schedule | Task 8 |
| Remove old services | Task 9 |
| Update `__init__.py` | Task 9 |

**No placeholders, no TBDs, all code is complete.**

**Type consistency:** `server_id: int`, `username: str`, `secret: str` used consistently across services and tasks. `instance_id: int` used for health check service (matches existing `VDSHealthCheckInfraService` and `sync_keys_to_vds_task` signatures).
