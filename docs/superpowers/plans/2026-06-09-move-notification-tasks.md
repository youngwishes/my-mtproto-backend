# Move Notification Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move three notification-related services and Celery tasks from `apps/vds` to `apps/notifications`, making app responsibilities explicit.

**Architecture:** Each service file is copied to `notifications/services/`, with test imports updated to reflect new module paths. Tasks are added to `notifications/tasks.py` and removed from `vds/tasks.py`. The Celery beat schedule is updated for the two scheduled tasks. Old files are deleted only after new tests are green.

**Tech Stack:** Django, Celery, pytest/unittest, `mock.patch`

---

## File Map

| Action | Path |
|---|---|
| Create | `src/apps/notifications/services/notify_before_removing_daily_service.py` |
| Create | `src/apps/notifications/services/notify_before_removing_hour_before_service.py` |
| Create | `src/apps/notifications/services/broadcast_proxy_links_service.py` |
| Modify | `src/apps/notifications/services/__init__.py` |
| Modify | `src/apps/notifications/tasks.py` |
| Create | `src/apps/notifications/tests/test_notify_before_removing_daily_task.py` |
| Create | `src/apps/notifications/tests/test_notify_before_removing_hour_before_task.py` |
| Create | `src/apps/notifications/tests/test_notify_before_removing_hour_before_service.py` |
| Create | `src/apps/notifications/tests/test_broadcast_proxy_links_service.py` |
| Create | `src/apps/notifications/tests/test_broadcast_proxy_links_task.py` |
| Modify | `src/apps/vds/tasks.py` |
| Modify | `src/apps/vds/services/__init__.py` |
| Modify | `src/config/settings/celery.py` |
| Delete | `src/apps/vds/services/notify_before_removing_daily_service.py` |
| Delete | `src/apps/vds/services/notify_before_removing_hour_before_service.py` |
| Delete | `src/apps/vds/services/broadcast_proxy_links_service.py` |
| Delete | `src/apps/vds/tests/test_tasks/test_notify_user_task.py` |
| Delete | `src/apps/vds/tests/test_tasks/test_broadcast_proxy_links_task.py` |
| Delete | `src/apps/vds/tests/test_services/test_notify_before_removing_hour_before_service.py` |
| Delete | `src/apps/vds/tests/test_services/test_broadcast_proxy_links_service.py` |

---

### Task 1: Move `notify_before_removing_daily_service` + its Celery task

**Files:**
- Create: `src/apps/notifications/services/notify_before_removing_daily_service.py`
- Create: `src/apps/notifications/tests/test_notify_before_removing_daily_task.py`
- Modify: `src/apps/notifications/services/__init__.py`
- Modify: `src/apps/notifications/tasks.py`

- [ ] **Step 1: Write the failing test**

Create `src/apps/notifications/tests/test_notify_before_removing_daily_task.py`:

```python
from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.notifications.tasks import notify_before_removing_daily
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory

_SERVICE_MODULE = "apps.notifications.services.notify_before_removing_daily_service"


class TestNotifyBeforeRemovingDailyTask(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory(username="123456789")
        self.key = MTPRotoKeyFactory(user=self.user, vds=self.server)

    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_does_not_notify_when_key_expires_today(self, mock_send, mock_get_template) -> None:
        notify_before_removing_daily()
        self.assertEqual(mock_send.call_count, 0)

    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_does_not_notify_when_key_expires_in_two_days(self, mock_send, mock_get_template) -> None:
        self.key.expired_date = timezone.now() + timedelta(days=2)
        self.key.save()
        notify_before_removing_daily()
        self.assertEqual(mock_send.call_count, 0)

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_notifies_user_once_when_key_expires_tomorrow(self, mock_send, mock_get_template, _time) -> None:
        mock_rendered = mock.Mock()
        mock_rendered.text = "Your link expires soon"
        mock_rendered.markup = None
        mock_get_template.return_value.render.return_value = mock_rendered

        self.key.expired_date = timezone.now() + timedelta(days=1)
        self.key.save()
        notify_before_removing_daily()
        self.assertEqual(mock_send.call_count, 1)
        notify_before_removing_daily()
        self.assertEqual(mock_send.call_count, 1)  # user_notified flag prevents re-send
```

- [ ] **Step 2: Run test to verify it fails**

```
cd src && python -m pytest apps/notifications/tests/test_notify_before_removing_daily_task.py -v
```

Expected: `ImportError` — `notify_before_removing_daily` not yet in `apps.notifications.tasks`.

- [ ] **Step 3: Create the service file**

Create `src/apps/notifications/services/notify_before_removing_daily_service.py` with the exact same content as the current `vds` version:

```python
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import timedelta
from typing import final

from django.conf import settings
from django.utils import html, timezone

from apps.core.telegram.transport import send_telegram_message
from apps.notifications.selectors import get_template
from apps.vds.selectors import get_unnotified_keys_expiring_on_date


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class NotifyBeforeRemovingDailyService:
    def __call__(self) -> None:
        target_date = (timezone.now() + timedelta(days=1)).date()
        queryset = get_unnotified_keys_expiring_on_date(date=target_date)

        template = get_template(slug="before_expiry_1day")
        for key in queryset:
            try:
                message = template.render()
                send_telegram_message(chat_id=int(key.user.username), text=message.text, markup=message.markup)
                key.user_notified = True
                key.save(update_fields=["user_notified"])
                time.sleep(0.5)
            except Exception as exc:
                escaped_error = html.escape(str(exc))
                send_telegram_message(
                    chat_id=int(settings.MY_TELEGRAM_ID),
                    text=(
                        "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                        "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                        "📋 <b>Детали:</b>\n"
                        f"- Не удалось уведомить пользователя о завтрашнем удалении ссылки.\n"
                        f"- Пользователь — {key.user.username}\n\n"
                        f"<code>{escaped_error}</code>\n\n"
                        "⚙️ <i>Возможно, требуется внимание команды</i>"
                    ),
                )


def get_notify_before_removing_daily_service() -> NotifyBeforeRemovingDailyService:
    return NotifyBeforeRemovingDailyService()
```

- [ ] **Step 4: Export the service from `notifications/services/__init__.py`**

Replace the full file content:

```python
from apps.notifications.services.notify_before_removing_daily_service import (
    NotifyBeforeRemovingDailyService,
    get_notify_before_removing_daily_service,
)
from apps.notifications.services.send_mailing_service import SendMailingService
from apps.notifications.services.send_notification_service import SendNotificationService

__all__ = [
    "NotifyBeforeRemovingDailyService",
    "get_notify_before_removing_daily_service",
    "SendNotificationService",
    "SendMailingService",
]
```

- [ ] **Step 5: Add the task to `notifications/tasks.py`**

```python
from __future__ import annotations

from celery import shared_task


@shared_task
def send_mailing_task(mailing_id: int) -> None:
    from apps.notifications.selectors import get_mailing_by_id
    from apps.notifications.services.send_mailing_service import SendMailingService

    mailing = get_mailing_by_id(mailing_id=mailing_id)
    SendMailingService(mailing=mailing)()


@shared_task
def notify_before_removing_daily() -> None:
    from apps.notifications.services import get_notify_before_removing_daily_service

    get_notify_before_removing_daily_service()()
```

- [ ] **Step 6: Run test to verify it passes**

```
cd src && python -m pytest apps/notifications/tests/test_notify_before_removing_daily_task.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 7: Commit**

```
git add src/apps/notifications/services/notify_before_removing_daily_service.py \
        src/apps/notifications/services/__init__.py \
        src/apps/notifications/tasks.py \
        src/apps/notifications/tests/test_notify_before_removing_daily_task.py
git commit -m "feat(notifications): move notify_before_removing_daily service and task"
```

---

### Task 2: Move `notify_before_removing_hour_before_service` + its task

**Files:**
- Create: `src/apps/notifications/services/notify_before_removing_hour_before_service.py`
- Create: `src/apps/notifications/tests/test_notify_before_removing_hour_before_service.py`
- Create: `src/apps/notifications/tests/test_notify_before_removing_hour_before_task.py`
- Modify: `src/apps/notifications/services/__init__.py`
- Modify: `src/apps/notifications/tasks.py`

- [ ] **Step 1: Write the failing service test**

Create `src/apps/notifications/tests/test_notify_before_removing_hour_before_service.py`:

```python
from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.notifications.services import get_notify_before_removing_hour_before_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory

_SERVICE_MODULE = "apps.notifications.services.notify_before_removing_hour_before_service"


class TestNotifyBeforeRemovingHourBeforeService(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory(username="123456789")
        self.key = MTPRotoKeyFactory(user=self.user, vds=self.server)

    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_does_not_notify_for_key_expiring_tomorrow(self, mock_send, _get_template) -> None:
        self.key.expired_date = timezone.now() + timedelta(days=1)
        self.key.save()

        get_notify_before_removing_hour_before_service()()

        mock_send.assert_not_called()

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_sends_message_to_user_for_key_expiring_today(self, mock_send, mock_get_template, _time) -> None:
        mock_rendered = mock.Mock()
        mock_rendered.text = "Your key expires in 1 hour"
        mock_rendered.markup = None
        mock_get_template.return_value.render.return_value = mock_rendered

        self.key.expired_date = timezone.now()
        self.key.save()

        get_notify_before_removing_hour_before_service()()

        mock_send.assert_called_once_with(
            chat_id=int(self.user.username),
            text=mock_rendered.text,
            markup=mock_rendered.markup,
        )

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_notifies_admin_on_error_and_continues(self, mock_send, mock_get_template, _time) -> None:
        second_user = SystemUserFactory(username="987654321")
        MTPRotoKeyFactory(user=second_user, vds=self.server, expired_date=timezone.now())
        self.key.expired_date = timezone.now()
        self.key.save()

        mock_get_template.return_value.render.side_effect = Exception("send failed")

        get_notify_before_removing_hour_before_service()()

        self.assertEqual(mock_send.call_count, 2)
```

- [ ] **Step 2: Write the failing task test**

Create `src/apps/notifications/tests/test_notify_before_removing_hour_before_task.py`:

```python
from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.notifications.tasks import notify_before_removing_daily_hour_before
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory

_SERVICE_MODULE = "apps.notifications.services.notify_before_removing_hour_before_service"


class TestNotifyBeforeRemovingHourBeforeTask(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory(username="123456789")
        self.key = MTPRotoKeyFactory(user=self.user, vds=self.server)

    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_does_not_notify_when_no_keys_expiring_today(self, mock_send, _get_template) -> None:
        notify_before_removing_daily_hour_before()
        mock_send.assert_not_called()

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_notifies_user_for_key_expiring_today(self, mock_send, mock_get_template, _time) -> None:
        mock_rendered = mock.Mock()
        mock_rendered.text = "Your key expires in 1 hour"
        mock_rendered.markup = None
        mock_get_template.return_value.render.return_value = mock_rendered

        self.key.expired_date = timezone.now()
        self.key.save()

        notify_before_removing_daily_hour_before()

        mock_send.assert_called_once()
```

- [ ] **Step 3: Run tests to verify they fail**

```
cd src && python -m pytest apps/notifications/tests/test_notify_before_removing_hour_before_service.py apps/notifications/tests/test_notify_before_removing_hour_before_task.py -v
```

Expected: `ImportError` — service not in `apps.notifications.services` yet.

- [ ] **Step 4: Create the service file**

Create `src/apps/notifications/services/notify_before_removing_hour_before_service.py`:

```python
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import final

from django.conf import settings
from django.utils import html, timezone

from apps.core.telegram.transport import send_telegram_message
from apps.notifications.selectors import get_template
from apps.vds.selectors import get_keys_expiring_on_date


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class NotifyBeforeRemovingHourBeforeService:
    def __call__(self) -> None:
        queryset = get_keys_expiring_on_date(date=timezone.now().date())
        template = get_template(slug="before_expiry_1hour")
        for key in queryset:
            try:
                message = template.render()
                send_telegram_message(chat_id=int(key.user.username), text=message.text, markup=message.markup)
                time.sleep(1)
            except Exception as exc:
                escaped_error = html.escape(str(exc))
                send_telegram_message(
                    chat_id=int(settings.MY_TELEGRAM_ID),
                    text=(
                        "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                        "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                        "📋 <b>Детали:</b>\n"
                        f"- Не удалось уведомить пользователя о завтрашнем удалении ссылки.\n"
                        f"- Пользователь — {key.user.username}\n\n"
                        f"<code>{escaped_error}</code>\n\n"
                        "⚙️ <i>Возможно, требуется внимание команды</i>"
                    ),
                )


def get_notify_before_removing_hour_before_service() -> NotifyBeforeRemovingHourBeforeService:
    return NotifyBeforeRemovingHourBeforeService()
```

- [ ] **Step 5: Export from `notifications/services/__init__.py`**

```python
from apps.notifications.services.notify_before_removing_daily_service import (
    NotifyBeforeRemovingDailyService,
    get_notify_before_removing_daily_service,
)
from apps.notifications.services.notify_before_removing_hour_before_service import (
    NotifyBeforeRemovingHourBeforeService,
    get_notify_before_removing_hour_before_service,
)
from apps.notifications.services.send_mailing_service import SendMailingService
from apps.notifications.services.send_notification_service import SendNotificationService

__all__ = [
    "NotifyBeforeRemovingDailyService",
    "get_notify_before_removing_daily_service",
    "NotifyBeforeRemovingHourBeforeService",
    "get_notify_before_removing_hour_before_service",
    "SendNotificationService",
    "SendMailingService",
]
```

- [ ] **Step 6: Add task to `notifications/tasks.py`**

```python
from __future__ import annotations

from celery import shared_task


@shared_task
def send_mailing_task(mailing_id: int) -> None:
    from apps.notifications.selectors import get_mailing_by_id
    from apps.notifications.services.send_mailing_service import SendMailingService

    mailing = get_mailing_by_id(mailing_id=mailing_id)
    SendMailingService(mailing=mailing)()


@shared_task
def notify_before_removing_daily() -> None:
    from apps.notifications.services import get_notify_before_removing_daily_service

    get_notify_before_removing_daily_service()()


@shared_task
def notify_before_removing_daily_hour_before() -> None:
    from apps.notifications.services import get_notify_before_removing_hour_before_service

    get_notify_before_removing_hour_before_service()()
```

- [ ] **Step 7: Run tests to verify they pass**

```
cd src && python -m pytest apps/notifications/tests/test_notify_before_removing_hour_before_service.py apps/notifications/tests/test_notify_before_removing_hour_before_task.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 8: Commit**

```
git add src/apps/notifications/services/notify_before_removing_hour_before_service.py \
        src/apps/notifications/services/__init__.py \
        src/apps/notifications/tasks.py \
        src/apps/notifications/tests/test_notify_before_removing_hour_before_service.py \
        src/apps/notifications/tests/test_notify_before_removing_hour_before_task.py
git commit -m "feat(notifications): move notify_before_removing_hour_before service and task"
```

---

### Task 3: Move `broadcast_proxy_links_service` + task + both tests

**Files:**
- Create: `src/apps/notifications/services/broadcast_proxy_links_service.py`
- Create: `src/apps/notifications/tests/test_broadcast_proxy_links_service.py`
- Create: `src/apps/notifications/tests/test_broadcast_proxy_links_task.py`
- Modify: `src/apps/notifications/services/__init__.py`
- Modify: `src/apps/notifications/tasks.py`

- [ ] **Step 1: Write the failing service test**

Create `src/apps/notifications/tests/test_broadcast_proxy_links_service.py`:

```python
from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory

_SERVICE_MODULE = "apps.notifications.services.broadcast_proxy_links_service"


class TestBroadcastProxyLinksService(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory(username="123456789")
        self.key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.server,
            is_active=True,
            was_deleted=False,
            expired_date=timezone.now() + timedelta(days=10),
        )
        self.user.first_month_free_used = True
        self.user.save()

    def _get_service(self):
        from apps.notifications.services.broadcast_proxy_links_service import get_broadcast_proxy_links_service

        return get_broadcast_proxy_links_service()

    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_does_not_send_when_no_broadcast_keys(self, mock_send) -> None:
        self.key.is_active = False
        self.key.save()

        self._get_service()()

        mock_send.assert_not_called()

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_sends_message_to_user_with_proxy_link(self, mock_send, _time) -> None:
        self._get_service()()

        self.assertEqual(mock_send.call_count, 1)
        call_kwargs = mock_send.call_args
        self.assertEqual(call_kwargs.kwargs["chat_id"], int(self.user.username))

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_extends_key_expiry_by_3_days_after_sending(self, mock_send, _time) -> None:
        original_expiry = self.key.expired_date

        self._get_service()()

        self.key.refresh_from_db()
        self.assertEqual(self.key.expired_date, original_expiry + timedelta(days=3))

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_notifies_admin_on_error_and_continues_with_next_key(self, mock_send, _time) -> None:
        second_user = SystemUserFactory(username="987654321")
        second_user.first_month_free_used = True
        second_user.save()
        MTPRotoKeyFactory(
            user=second_user,
            vds=self.server,
            is_active=True,
            was_deleted=False,
            expired_date=timezone.now() + timedelta(days=10),
        )

        mock_send.side_effect = [Exception("telegram error"), None, None]

        self._get_service()()

        self.assertEqual(mock_send.call_count, 3)

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_failed_key_expiry_not_extended_on_error(self, mock_send, _time) -> None:
        original_expiry = self.key.expired_date
        mock_send.side_effect = Exception("telegram error")

        self._get_service()()

        self.key.refresh_from_db()
        self.assertEqual(self.key.expired_date, original_expiry)
```

- [ ] **Step 2: Write the failing task test**

Create `src/apps/notifications/tests/test_broadcast_proxy_links_task.py`:

```python
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.notifications.tasks import broadcast_proxy_links_task
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestBroadcastProxyLinksTask(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory(first_month_free_used=True, username="123456789")
        self.expired_date = timezone.now() + timedelta(days=10)
        self.key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.server,
            expired_date=self.expired_date,
        )

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_sends_message_and_extends_key(self, mock_send):
        broadcast_proxy_links_task()

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["chat_id"], int(self.user.username))
        self.assertIn("markup", call_kwargs)

        self.key.refresh_from_db()
        self.assertAlmostEqual(
            self.key.expired_date,
            self.expired_date + timedelta(days=3),
            delta=timedelta(seconds=5),
        )

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_skips_users_without_first_month_free(self, mock_send):
        user_no_free = SystemUserFactory(first_month_free_used=False, username="987654321")
        MTPRotoKeyFactory(
            user=user_no_free,
            vds=self.server,
            expired_date=timezone.now() + timedelta(days=10),
        )

        broadcast_proxy_links_task()

        self.assertEqual(mock_send.call_count, 1)
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["chat_id"], int(self.user.username))

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_skips_inactive_keys(self, mock_send):
        self.key.is_active = False
        self.key.save(update_fields=["is_active"])

        broadcast_proxy_links_task()

        mock_send.assert_not_called()

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_skips_deleted_keys(self, mock_send):
        self.key.was_deleted = True
        self.key.save(update_fields=["was_deleted"])

        broadcast_proxy_links_task()

        mock_send.assert_not_called()

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_skips_expired_keys(self, mock_send):
        self.key.expired_date = timezone.now() - timedelta(days=1)
        self.key.save(update_fields=["expired_date"])

        broadcast_proxy_links_task()

        mock_send.assert_not_called()

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_does_not_extend_on_telegram_error(self, mock_send):
        mock_send.side_effect = [Exception("Telegram API error"), None]

        broadcast_proxy_links_task()

        self.key.refresh_from_db()
        self.assertAlmostEqual(
            self.key.expired_date,
            self.expired_date,
            delta=timedelta(seconds=5),
        )

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_notifies_admin_on_error(self, mock_send):
        mock_send.side_effect = [Exception("Telegram API error"), None]

        broadcast_proxy_links_task()

        self.assertEqual(mock_send.call_count, 2)
        admin_call_kwargs = mock_send.call_args_list[1].kwargs
        self.assertIn("Системное оповещение", admin_call_kwargs["text"])

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_sends_to_multiple_users(self, mock_send):
        user2 = SystemUserFactory(first_month_free_used=True, username="555555555")
        key2 = MTPRotoKeyFactory(
            user=user2,
            vds=self.server,
            expired_date=timezone.now() + timedelta(days=5),
        )

        broadcast_proxy_links_task()

        self.assertEqual(mock_send.call_count, 2)
        self.key.refresh_from_db()
        key2.refresh_from_db()
        self.assertAlmostEqual(
            self.key.expired_date,
            self.expired_date + timedelta(days=3),
            delta=timedelta(seconds=5),
        )
        self.assertAlmostEqual(
            key2.expired_date,
            timezone.now() + timedelta(days=5) + timedelta(days=3),
            delta=timedelta(seconds=5),
        )

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_continues_after_error_for_one_user(self, mock_send):
        user2 = SystemUserFactory(first_month_free_used=True, username="444444444")
        key2_expired = timezone.now() + timedelta(days=5)
        key2 = MTPRotoKeyFactory(
            user=user2,
            vds=self.server,
            expired_date=key2_expired,
        )

        mock_send.side_effect = [Exception("blocked by user"), None, None]

        broadcast_proxy_links_task()

        self.key.refresh_from_db()
        self.assertAlmostEqual(
            self.key.expired_date,
            self.expired_date,
            delta=timedelta(seconds=5),
        )

        key2.refresh_from_db()
        self.assertAlmostEqual(
            key2.expired_date,
            key2_expired + timedelta(days=3),
            delta=timedelta(seconds=5),
        )
```

- [ ] **Step 3: Run tests to verify they fail**

```
cd src && python -m pytest apps/notifications/tests/test_broadcast_proxy_links_service.py apps/notifications/tests/test_broadcast_proxy_links_task.py -v
```

Expected: `ImportError` — service not yet in `apps.notifications.services`.

- [ ] **Step 4: Create the service file**

Create `src/apps/notifications/services/broadcast_proxy_links_service.py`:

```python
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import timedelta
from typing import final

from django.conf import settings
from django.utils import html

from apps.core.telegram.transport import send_telegram_message
from apps.vds.selectors import get_active_broadcast_keys


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class BroadcastProxyLinksService:
    def __call__(self, *, testing: bool = False) -> None:
        from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

        keys = get_active_broadcast_keys(testing=testing)

        sent_count = 0
        for key in keys:
            try:
                send_telegram_message(
                    chat_id=int(key.user.username),
                    text=(
                        "✨ <b>Привет!</b>\n\n"
                        "В последнее время часть ссылок могла работать нестабильно из-за блокировок. "
                        "Мы долго работали над решением — и нам удалось <b>полностью обойти ограничения.</b>\n\n"
                        "Сейчас всё работает стабильно, и мы решили продлить твою ссылку на <b>3 дня</b> "
                        "в качестве компенсации за неудобства.\n\n"
                        f"👇 <b>Твоя ссылка (действует до {(key.expired_date + timedelta(days=3)).strftime('%d.%m.%Y')}):</b>"
                    ),
                    markup=InlineKeyboardMarkup(
                        keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="🇳🇱 Подключиться",
                                    url=key.get_proxy_link(),
                                )
                            ]
                        ]
                    ),
                )
                key.expired_date = key.expired_date + timedelta(days=3)
                key.save(update_fields=["expired_date"])
                sent_count += 1
                if sent_count % 10 == 0:
                    time.sleep(1)
            except Exception as exc:
                try:
                    escaped_error = html.escape(str(exc))
                    send_telegram_message(
                        chat_id=int(settings.MY_TELEGRAM_ID),
                        text=(
                            "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                            "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                            "📋 <b>Детали:</b>\n"
                            f"- Не удалось отправить broadcast пользователю\n"
                            f"- Пользователь — {key.user.username}\n\n"
                            f"<code>{escaped_error}</code>\n\n"
                            "⚙️ <i>Возможно, требуется внимание команды</i>"
                        ),
                    )
                except Exception:
                    pass


def get_broadcast_proxy_links_service() -> BroadcastProxyLinksService:
    return BroadcastProxyLinksService()
```

- [ ] **Step 5: Export from `notifications/services/__init__.py`**

```python
from apps.notifications.services.broadcast_proxy_links_service import (
    BroadcastProxyLinksService,
    get_broadcast_proxy_links_service,
)
from apps.notifications.services.notify_before_removing_daily_service import (
    NotifyBeforeRemovingDailyService,
    get_notify_before_removing_daily_service,
)
from apps.notifications.services.notify_before_removing_hour_before_service import (
    NotifyBeforeRemovingHourBeforeService,
    get_notify_before_removing_hour_before_service,
)
from apps.notifications.services.send_mailing_service import SendMailingService
from apps.notifications.services.send_notification_service import SendNotificationService

__all__ = [
    "BroadcastProxyLinksService",
    "get_broadcast_proxy_links_service",
    "NotifyBeforeRemovingDailyService",
    "get_notify_before_removing_daily_service",
    "NotifyBeforeRemovingHourBeforeService",
    "get_notify_before_removing_hour_before_service",
    "SendNotificationService",
    "SendMailingService",
]
```

- [ ] **Step 6: Add task to `notifications/tasks.py`**

```python
from __future__ import annotations

from celery import shared_task


@shared_task
def send_mailing_task(mailing_id: int) -> None:
    from apps.notifications.selectors import get_mailing_by_id
    from apps.notifications.services.send_mailing_service import SendMailingService

    mailing = get_mailing_by_id(mailing_id=mailing_id)
    SendMailingService(mailing=mailing)()


@shared_task
def notify_before_removing_daily() -> None:
    from apps.notifications.services import get_notify_before_removing_daily_service

    get_notify_before_removing_daily_service()()


@shared_task
def notify_before_removing_daily_hour_before() -> None:
    from apps.notifications.services import get_notify_before_removing_hour_before_service

    get_notify_before_removing_hour_before_service()()


@shared_task
def broadcast_proxy_links_task(testing: bool = False) -> None:
    from apps.notifications.services import get_broadcast_proxy_links_service

    get_broadcast_proxy_links_service()(testing=testing)
```

- [ ] **Step 7: Run tests to verify they pass**

```
cd src && python -m pytest apps/notifications/tests/test_broadcast_proxy_links_service.py apps/notifications/tests/test_broadcast_proxy_links_task.py -v
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```
git add src/apps/notifications/services/broadcast_proxy_links_service.py \
        src/apps/notifications/services/__init__.py \
        src/apps/notifications/tasks.py \
        src/apps/notifications/tests/test_broadcast_proxy_links_service.py \
        src/apps/notifications/tests/test_broadcast_proxy_links_task.py
git commit -m "feat(notifications): move broadcast_proxy_links service and task"
```

---

### Task 4: Clean up `vds` app — remove old tasks, services, files, update celery

**Files:**
- Modify: `src/apps/vds/tasks.py`
- Modify: `src/apps/vds/services/__init__.py`
- Modify: `src/config/settings/celery.py`
- Delete: `src/apps/vds/services/notify_before_removing_daily_service.py`
- Delete: `src/apps/vds/services/notify_before_removing_hour_before_service.py`
- Delete: `src/apps/vds/services/broadcast_proxy_links_service.py`
- Delete: `src/apps/vds/tests/test_tasks/test_notify_user_task.py`
- Delete: `src/apps/vds/tests/test_tasks/test_broadcast_proxy_links_task.py`
- Delete: `src/apps/vds/tests/test_services/test_notify_before_removing_hour_before_service.py`
- Delete: `src/apps/vds/tests/test_services/test_broadcast_proxy_links_service.py`

- [ ] **Step 1: Remove the 3 moved tasks from `vds/tasks.py`**

Replace full file content with only the remaining VDS tasks:

```python
from __future__ import annotations

from celery import shared_task


@shared_task
def migrate_vds_keys_task(from_instance_id: int) -> None:
    from apps.vds.services import get_migrate_vds_keys_service

    get_migrate_vds_keys_service()(from_instance_id=from_instance_id)


@shared_task
def remove_user_keys_daily():
    from apps.vds.services import get_remove_expired_keys_daily_service

    get_remove_expired_keys_daily_service()()


@shared_task
def add_key_to_another_vds_instances_task(exclude: int, username: str, secret: str) -> None:
    from apps.vds.services import get_add_key_to_another_vds_instances_service

    get_add_key_to_another_vds_instances_service()(exclude=exclude, username=username, secret=secret)


@shared_task
def remove_key_from_another_vds_instances_task(server: int, keys_id: list[int]) -> None:
    from apps.vds.services import get_remove_keys_from_vds_instance_infra_service

    get_remove_keys_from_vds_instance_infra_service()(server_id=server, keys_ids=keys_id)
```

- [ ] **Step 2: Remove the 3 moved services from `vds/services/__init__.py`**

Replace full file content:

```python
from apps.vds.services.add_key_to_another_vds_infra_service import (
    AddKeyToAnotherVdsInfraService,
    get_add_key_to_another_vds_instances_service,
)
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

__all__ = [
    "AddKeyToAnotherVdsInfraService",
    "get_add_key_to_another_vds_instances_service",
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
]
```

- [ ] **Step 3: Update Celery beat schedule in `config/settings/celery.py`**

Replace full file content:

```python
import os

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
}
```

- [ ] **Step 4: Delete old service files from `vds/services/`**

```bash
rm src/apps/vds/services/notify_before_removing_daily_service.py
rm src/apps/vds/services/notify_before_removing_hour_before_service.py
rm src/apps/vds/services/broadcast_proxy_links_service.py
```

- [ ] **Step 5: Delete old test files from `vds/tests/`**

```bash
rm src/apps/vds/tests/test_tasks/test_notify_user_task.py
rm src/apps/vds/tests/test_tasks/test_broadcast_proxy_links_task.py
rm src/apps/vds/tests/test_services/test_notify_before_removing_hour_before_service.py
rm src/apps/vds/tests/test_services/test_broadcast_proxy_links_service.py
```

- [ ] **Step 6: Run the full test suite**

```
cd src && make test
```

Expected: all tests pass, no import errors, no reference to the removed modules.

- [ ] **Step 7: Commit**

```
git add -u
git commit -m "refactor(vds): remove notification tasks/services moved to notifications app"
```
