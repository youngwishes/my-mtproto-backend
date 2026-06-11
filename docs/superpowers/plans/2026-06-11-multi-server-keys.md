# Multi-Server Keys Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show users proxy links for every active VDS instance so Telegram can transparently fail over to a backup server.

**Architecture:** Keep one `MTPRotoKey` per user in the DB; generate proxy links on-the-fly for all active `VDSInstance` records using the stored `token` and `tls_domain` (identical across all VDS). A new `GET /api/v1/users/my-servers/` endpoint returns the list; the bot renders it as a "Мои серверы" screen accessible from the main menu and after key issuance.

**Tech Stack:** Django 6 + DRF, factory_boy, Python `unittest.mock`, Aiogram 3.x, httpx.

---

## Task 1: `MTPRotoKey.get_proxy_link_for_server`

**Files:**
- Modify: `src/apps/vds/models.py`
- Modify: `src/apps/vds/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `src/apps/vds/tests/test_models.py`:

```python
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestMTPRotoKeyMethods(TestCase):
    def test_get_proxy_link_for_server_uses_given_server_name(self) -> None:
        key = MTPRotoKeyFactory(
            token="abc123",
            tls_domain="petrovich.ru",
        )
        link = key.get_proxy_link_for_server("de1")
        domain_hex = "petrovich.ru".encode("utf-8").hex()
        expected_secret = f"eeabc123{domain_hex}"
        self.assertEqual(
            link,
            f"tg://proxy?server=de1.beatvault.ru&port=443&secret={expected_secret}",
        )

    def test_get_proxy_link_for_server_differs_from_primary(self) -> None:
        key = MTPRotoKeyFactory(
            token="abc123",
            tls_domain="petrovich.ru",
            node_number="nl1",
        )
        primary_link = key.get_proxy_link()
        replica_link = key.get_proxy_link_for_server("de1")
        self.assertNotEqual(primary_link, replica_link)
        self.assertIn("nl1.beatvault.ru", primary_link)
        self.assertIn("de1.beatvault.ru", replica_link)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/youngwishes/PyProjects/my-mtproto-backend
make test ARGS="apps.vds.tests.test_models.TestMTPRotoKeyMethods"
```

Expected: `AttributeError: 'MTPRotoKey' object has no attribute 'get_proxy_link_for_server'`

- [ ] **Step 3: Add method to `MTPRotoKey`**

In `src/apps/vds/models.py`, add after `get_proxy_link`:

```python
def get_proxy_link_for_server(self, server_name: str) -> str:
    secret = self.get_secret_token()
    return f"tg://proxy?server={server_name}.beatvault.ru&port=443&secret={secret}"
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
make test ARGS="apps.vds.tests.test_models.TestMTPRotoKeyMethods"
```

Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/apps/vds/models.py src/apps/vds/tests/test_models.py
git commit -m "feat(vds): add MTPRotoKey.get_proxy_link_for_server method"
```

---

## Task 2: `VDSInstance.location` field + migration

**Files:**
- Modify: `src/apps/vds/models.py`
- Modify: `src/apps/vds/tests/factories.py`
- Create: migration (auto-generated as `0016_vdsinstance_location.py`)

- [ ] **Step 1: Add field to `VDSInstance`**

In `src/apps/vds/models.py`, inside `VDSInstance`, after `is_keys_available`:

```python
location = models.CharField("геолокация", default="", blank=True)
```

- [ ] **Step 2: Generate and apply migration**

```bash
cd src && python manage.py makemigrations vds --name vdsinstance_location
python manage.py migrate
```

Expected: new migration `0016_vdsinstance_location.py` created and applied.

- [ ] **Step 3: Update factory**

In `src/apps/vds/tests/factories.py`, add `location` to `VDSInstanceFactory`:

```python
class VDSInstanceFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"vds-server-{n}")
    number = factory.Sequence(lambda n: n + 2)
    ip_address = factory.Sequence(lambda n: f"192.168.1.{n + 1}")
    internal_ip_address = factory.Sequence(lambda n: f"192.168.2.{n + 1}")
    user_limit = 30
    is_keys_available = True
    port = 8000
    location = factory.Sequence(lambda n: f"🌍 Server {n}")

    class Meta:
        model = VDSInstance
```

- [ ] **Step 4: Run full VDS test suite to confirm no regressions**

```bash
make test ARGS="apps.vds"
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/apps/vds/models.py src/apps/vds/tests/factories.py src/apps/vds/migrations/
git commit -m "feat(vds): add VDSInstance.location field"
```

---

## Task 3: `NotificationTemplate.button_callback_data` + render update

**Files:**
- Modify: `src/apps/notifications/models.py`
- Modify: `src/apps/notifications/tests/factories.py`
- Modify: `src/apps/notifications/tests/test_models.py`
- Create: migration (auto-generated as `0006_notificationtemplate_button_callback_data.py`)

- [ ] **Step 1: Write the failing tests**

Add to the existing `TestNotificationTemplateRender` class in `src/apps/notifications/tests/test_models.py`:

```python
def test_render_with_callback_button(self) -> None:
    template = NotificationTemplateFactory(
        text="Нажми кнопку",
        button_text="📡 Мои серверы",
        button_url="",
        button_callback_data="my_servers",
    )
    result = template.render()
    self.assertIsNotNone(result.markup)
    button = result.markup.keyboard[0][0]
    self.assertEqual(button.text, "📡 Мои серверы")
    self.assertEqual(button.callback_data, "my_servers")
    self.assertIsNone(button.url)

def test_render_url_button_takes_priority_over_callback_data(self) -> None:
    template = NotificationTemplateFactory(
        text="Текст",
        button_text="Кнопка",
        button_url="https://example.com",
        button_callback_data="some_callback",
    )
    result = template.render()
    button = result.markup.keyboard[0][0]
    self.assertEqual(button.url, "https://example.com")
    self.assertIsNone(button.callback_data)
```

- [ ] **Step 2: Run to confirm failure**

```bash
make test ARGS="apps.notifications.tests.test_models.TestNotificationTemplateRender.test_render_with_callback_button"
```

Expected: `TypeError` — `button_callback_data` is an unexpected keyword argument.

- [ ] **Step 3: Add field to `NotificationTemplate`**

In `src/apps/notifications/models.py`, inside `NotificationTemplate`, after `button_url`:

```python
button_callback_data = models.CharField(
    "callback_data кнопки", max_length=128, blank=True, default=""
)
```

- [ ] **Step 4: Update `render()` in `NotificationTemplate`**

Replace the existing `if self.button_text and self.button_url:` block in `render()`:

```python
if self.button_text and self.button_url:
    keyboard_rows.append(
        [InlineKeyboardButton(
            text=self.button_text,
            url=self.button_url.format(**ctx),
        )]
    )
elif self.button_text and self.button_callback_data:
    keyboard_rows.append(
        [InlineKeyboardButton(
            text=self.button_text,
            callback_data=self.button_callback_data,
        )]
    )
```

- [ ] **Step 5: Update factory**

In `src/apps/notifications/tests/factories.py`, add `button_callback_data` to `NotificationTemplateFactory`:

```python
class NotificationTemplateFactory(factory.django.DjangoModelFactory):
    slug = factory.Sequence(lambda n: f"template-{n}")
    title = factory.Sequence(lambda n: f"Template {n}")
    text = "Default text"
    button_text = ""
    button_url = ""
    button_callback_data = ""
    include_payment_buttons = False

    class Meta:
        model = NotificationTemplate
```

- [ ] **Step 6: Generate and apply migration**

```bash
cd src && python manage.py makemigrations notifications --name notificationtemplate_button_callback_data
python manage.py migrate
```

Expected: new migration `0006_notificationtemplate_button_callback_data.py` created and applied.

- [ ] **Step 7: Run notifications test suite**

```bash
make test ARGS="apps.notifications"
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/apps/notifications/models.py src/apps/notifications/tests/factories.py \
        src/apps/notifications/tests/test_models.py src/apps/notifications/migrations/
git commit -m "feat(notifications): add button_callback_data to NotificationTemplate"
```

---

## Task 4: Update `CreatePaymentService` notification context

**Files:**
- Modify: `src/apps/payments/services/create_payment_service.py`
- Modify: `src/apps/payments/tests/test_create_payment_service.py`

- [ ] **Step 1: Write a failing test**

In `src/apps/payments/tests/test_create_payment_service.py`, add to `TestCreatePaymentService`:

```python
@responses.activate
@mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
@mock.patch("apps.notifications.services.send_notification_service.send_telegram_message")
def test_notification_context_contains_expired_date_not_link(
    self, mock_send: mock.Mock, _task: mock.Mock
) -> None:
    self._mock_vds_request()

    self.service(payment=self._make_payment(charge_id="charge_ctx"))

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args
    # send_telegram_message is called with text=rendered_text, so check the template context
    # by inspecting that the rendered message text does NOT contain a tg:// link
    # (link is no longer in the context)
    rendered_text = call_kwargs[1].get("text") or call_kwargs[0][1]
    self.assertNotIn("tg://proxy", rendered_text)
```

- [ ] **Step 2: Run to confirm the test passes already or understand baseline**

```bash
make test ARGS="apps.payments.tests.test_create_payment_service.TestCreatePaymentService.test_notification_context_contains_expired_date_not_link"
```

Note: this test may already fail because the current template passes `link` which renders `tg://proxy` in the template text. Understand the current output.

- [ ] **Step 3: Update `CreatePaymentService` to pass `expired_date` instead of `link`**

In `src/apps/payments/services/create_payment_service.py`, replace the `SendNotificationService` call:

```python
SendNotificationService(
    slug="proxy_purchased",
    context={"expired_date": key.expired_date.date().strftime("%d.%m.%y")},
)(chat_id=int(user.username))
```

- [ ] **Step 4: Run the full payments test suite**

```bash
make test ARGS="apps.payments"
```

Expected: all pass. (Existing tests that check `mock_send.assert_called_once()` remain valid — we're changing the context, not removing the call.)

- [ ] **Step 5: Commit**

```bash
git add src/apps/payments/services/create_payment_service.py \
        src/apps/payments/tests/test_create_payment_service.py
git commit -m "feat(payments): pass expired_date instead of link to proxy_purchased template"
```

---

## Task 5: DTOs + `GetMyServersService`

**Files:**
- Create: `src/apps/vds/services/dtos/my_servers_dto.py`
- Modify: `src/apps/vds/services/dtos/__init__.py`
- Create: `src/apps/vds/services/get_my_servers_service.py`
- Modify: `src/apps/vds/services/__init__.py`
- Create: `src/apps/vds/tests/test_get_my_servers_service.py`

- [ ] **Step 1: Create the DTOs**

Create `src/apps/vds/services/dtos/my_servers_dto.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class MyServerOut(BaseServiceDTO):
    """Один сервер в списке для пользователя."""

    location: str
    proxy_link: str


@dataclass(kw_only=True, frozen=True, slots=True)
class MyServersOut(BaseServiceDTO):
    """Ответ GetMyServersService: дата истечения + список серверов."""

    expired_date: str
    servers: list[MyServerOut]
```

- [ ] **Step 2: Export from DTOs `__init__`**

In `src/apps/vds/services/dtos/__init__.py`:

```python
from apps.vds.services.dtos.add_new_key_dto import VDSKeyResponseOut
from apps.vds.services.dtos.update_key_dto import UpdateKeyOut
from apps.vds.services.dtos.my_servers_dto import MyServerOut, MyServersOut

__all__ = [
    "VDSKeyResponseOut",
    "UpdateKeyOut",
    "MyServerOut",
    "MyServersOut",
]
```

- [ ] **Step 3: Write failing tests**

Create `src/apps/vds/tests/test_get_my_servers_service.py`:

```python
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.vds.exceptions import KeyDoesNotExist
from apps.vds.services.get_my_servers_service import get_my_servers_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory
from apps.users.tests.factories import SystemUserFactory


class TestGetMyServersService(TestCase):
    def setUp(self) -> None:
        self.service = get_my_servers_service()

    def test_returns_all_active_vds_links_for_user_with_key(self) -> None:
        user = SystemUserFactory(username="11111111")
        vds1 = VDSInstanceFactory(name="nl1", location="🇳🇱 Нидерланды", is_active=True)
        vds2 = VDSInstanceFactory(name="de1", location="🇩🇪 Германия", is_active=True)
        key = MTPRotoKeyFactory(
            user=user,
            vds=vds1,
            token="testtoken",
            tls_domain="petrovich.ru",
            expired_date=timezone.now() + timedelta(days=30),
            is_active=True,
            was_deleted=False,
        )

        result = self.service(username="11111111")

        self.assertEqual(result.expired_date, key.expired_date.date().strftime("%d.%m.%y"))
        self.assertEqual(len(result.servers), 2)
        locations = [s.location for s in result.servers]
        self.assertIn("🇳🇱 Нидерланды", locations)
        self.assertIn("🇩🇪 Германия", locations)
        for server in result.servers:
            self.assertIn("tg://proxy?server=", server.proxy_link)
            self.assertIn(".beatvault.ru", server.proxy_link)
            domain_hex = "petrovich.ru".encode("utf-8").hex()
            self.assertIn(f"eetesttoken{domain_hex}", server.proxy_link)

    def test_excludes_inactive_vds(self) -> None:
        user = SystemUserFactory(username="22222222")
        vds1 = VDSInstanceFactory(name="nl1", location="🇳🇱 Нидерланды", is_active=True)
        VDSInstanceFactory(name="de1", location="🇩🇪 Германия", is_active=False)
        MTPRotoKeyFactory(
            user=user,
            vds=vds1,
            expired_date=timezone.now() + timedelta(days=30),
            is_active=True,
            was_deleted=False,
        )

        result = self.service(username="22222222")

        self.assertEqual(len(result.servers), 1)
        self.assertEqual(result.servers[0].location, "🇳🇱 Нидерланды")

    def test_raises_when_user_not_found(self) -> None:
        with self.assertRaises(KeyDoesNotExist):
            self.service(username="nonexistent")

    def test_raises_when_user_has_no_active_key(self) -> None:
        user = SystemUserFactory(username="33333333")
        VDSInstanceFactory(is_active=True)

        with self.assertRaises(KeyDoesNotExist):
            self.service(username="33333333")

    def test_raises_when_key_is_expired(self) -> None:
        user = SystemUserFactory(username="44444444")
        vds = VDSInstanceFactory(is_active=True)
        MTPRotoKeyFactory(
            user=user,
            vds=vds,
            expired_date=timezone.now() - timedelta(days=1),
            is_active=True,
            was_deleted=False,
        )

        with self.assertRaises(KeyDoesNotExist):
            self.service(username="44444444")
```

- [ ] **Step 4: Run to confirm failure**

```bash
make test ARGS="apps.vds.tests.test_get_my_servers_service"
```

Expected: `ImportError` — `get_my_servers_service` not found.

- [ ] **Step 5: Implement `GetMyServersService`**

Create `src/apps/vds/services/get_my_servers_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import final

from apps.core.decorators import log_service_error
from apps.users.selectors import get_user_by_username
from apps.vds.exceptions import KeyDoesNotExist
from apps.vds.selectors import get_active_key, get_all_active_vds_instances
from apps.vds.services.dtos import MyServerOut, MyServersOut


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class GetMyServersService:
    """Возвращает proxy-ссылки пользователя для всех активных VDS."""

    @log_service_error
    def __call__(self, *, username: str) -> MyServersOut:
        user = get_user_by_username(username=username)
        if user is None:
            raise KeyDoesNotExist(telegram_id=username)
        key = get_active_key(user=user)
        if key is None:
            raise KeyDoesNotExist(telegram_id=username)
        servers = [
            MyServerOut(
                location=vds.location,
                proxy_link=key.get_proxy_link_for_server(vds.name),
            )
            for vds in get_all_active_vds_instances()
        ]
        return MyServersOut(
            expired_date=key.expired_date.date().strftime("%d.%m.%y"),
            servers=servers,
        )


def get_my_servers_service() -> GetMyServersService:
    return GetMyServersService()
```

- [ ] **Step 6: Export from services `__init__`**

In `src/apps/vds/services/__init__.py`, add at the end (before `__all__`):

```python
from apps.vds.services.get_my_servers_service import (
    GetMyServersService,
    get_my_servers_service,
)
```

And add to `__all__`:
```python
"GetMyServersService",
"get_my_servers_service",
```

- [ ] **Step 7: Run tests**

```bash
make test ARGS="apps.vds.tests.test_get_my_servers_service"
```

Expected: 5 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/apps/vds/services/dtos/my_servers_dto.py \
        src/apps/vds/services/dtos/__init__.py \
        src/apps/vds/services/get_my_servers_service.py \
        src/apps/vds/services/__init__.py \
        src/apps/vds/tests/test_get_my_servers_service.py
git commit -m "feat(vds): add GetMyServersService with MyServerOut/MyServersOut DTOs"
```

---

## Task 6: View + serializer + URL

**Files:**
- Create: `src/apps/users/api/v1/views/my_servers_view.py`
- Create: `src/apps/users/api/v1/serializers/my_servers_serializer.py`
- Modify: `src/apps/users/api/v1/views/__init__.py`
- Modify: `src/apps/users/api/v1/serializers/__init__.py`
- Modify: `src/apps/users/api/v1/urls.py`
- Create: `src/apps/vds/tests/test_my_servers_view.py`

- [ ] **Step 1: Write failing view tests**

Create `src/apps/vds/tests/test_my_servers_view.py`:

```python
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestMyServersView(APITestCase):
    url: str = reverse("my-servers")

    def setUp(self) -> None:
        self.user = SystemUserFactory(username="55555555")
        self.vds1 = VDSInstanceFactory(
            name="nl1", location="🇳🇱 Нидерланды", is_active=True
        )
        self.vds2 = VDSInstanceFactory(
            name="de1", location="🇩🇪 Германия", is_active=True
        )
        self.key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds1,
            token="viewtoken",
            tls_domain="petrovich.ru",
            expired_date=timezone.now() + timedelta(days=30),
            is_active=True,
            was_deleted=False,
        )

    def _post(self, data: dict | None = None) -> object:
        return self.client.post(
            path=self.url,
            data=data or {"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

    def test_returns_servers_for_user_with_active_key(self) -> None:
        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("expired_date", data)
        self.assertIn("servers", data)
        self.assertEqual(len(data["servers"]), 2)
        locations = [s["location"] for s in data["servers"]]
        self.assertIn("🇳🇱 Нидерланды", locations)
        self.assertIn("🇩🇪 Германия", locations)
        for server in data["servers"]:
            self.assertIn("tg://proxy", server["proxy_link"])

    def test_missing_bot_auth_token_returns_403(self) -> None:
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_without_active_key_returns_error(self) -> None:
        user_no_key = SystemUserFactory(username="66666666")
        VDSInstanceFactory(is_active=True)

        response = self._post(data={"username": "66666666"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())
```

- [ ] **Step 2: Run to confirm failure**

```bash
make test ARGS="apps.vds.tests.test_my_servers_view"
```

Expected: `NoReverseMatch` — `my-servers` URL not registered yet.

- [ ] **Step 3: Create serializer**

Create `src/apps/users/api/v1/serializers/my_servers_serializer.py`:

```python
from rest_framework import serializers


class MyServersSerializer(serializers.Serializer):
    username = serializers.CharField()
```

- [ ] **Step 4: Create view**

Create `src/apps/users/api/v1/views/my_servers_view.py`:

```python
from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.api.v1.serializers import MyServersSerializer
from apps.users.permissions import BotAuthToken
from apps.vds.services import get_my_servers_service


class MyServersView(APIView):
    permission_classes = (BotAuthToken,)

    def post(self, request: Request) -> Response:
        serializer = MyServersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = get_my_servers_service()
        result = service(username=serializer.validated_data["username"])
        return Response(result.asdict(), status=status.HTTP_200_OK)
```

- [ ] **Step 5: Export view and serializer**

In `src/apps/users/api/v1/views/__init__.py`:

```python
from .first_free_link_view import CreateFirstFreeLinkView, CheckFirstFreeLinkView
from .referral_cabinet_view import ReferralCabinetView, GetReferralLinkView
from .update_key_view import UpdateKeyView
from .my_servers_view import MyServersView
```

In `src/apps/users/api/v1/serializers/__init__.py`:

```python
from .first_free_link_serializer import (
    FirstFreeLinkSerializer,
    CheckFirstFreeLinkSerializer,
)
from .referral_cabinet_serializer import (
    ReferralCabinetSerializer,
    GetReferralLinkSerializer,
)
from .update_key_serializer import (
    UpdateKeySerializer,
)
from .my_servers_serializer import (
    MyServersSerializer,
)
```

- [ ] **Step 6: Register URL**

In `src/apps/users/api/v1/urls.py`:

```python
from django.urls import path
from apps.users.api.v1.views import (
    CreateFirstFreeLinkView,
    CheckFirstFreeLinkView,
    ReferralCabinetView,
    GetReferralLinkView,
    UpdateKeyView,
    MyServersView,
)

urlpatterns = [
    path("first-free-link/", CreateFirstFreeLinkView.as_view(), name="first-free-link"),
    path(
        "check-first-free-link/",
        CheckFirstFreeLinkView.as_view(),
        name="check-first-free-link",
    ),
    path(
        "referral/cabinet/",
        ReferralCabinetView.as_view(),
        name="referral-cabinet",
    ),
    path("referral/link/", GetReferralLinkView.as_view(), name="get-referral-link"),
    path("update-link/", UpdateKeyView.as_view(), name="update-link"),
    path("my-servers/", MyServersView.as_view(), name="my-servers"),
]
```

- [ ] **Step 7: Run tests**

```bash
make test ARGS="apps.vds.tests.test_my_servers_view"
```

Expected: 3 tests PASS.

- [ ] **Step 8: Run full test suite to check for regressions**

```bash
make test
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add src/apps/users/api/v1/views/my_servers_view.py \
        src/apps/users/api/v1/views/__init__.py \
        src/apps/users/api/v1/serializers/my_servers_serializer.py \
        src/apps/users/api/v1/serializers/__init__.py \
        src/apps/users/api/v1/urls.py \
        src/apps/vds/tests/test_my_servers_view.py
git commit -m "feat(users): add POST /api/v1/users/my-servers/ endpoint"
```

---

## Task 7: Bot service `GetMyServersService`

**Files:**
- Create: `bot/src/services/get_my_servers_service.py`
- Modify: `bot/src/services/__init__.py`

- [ ] **Step 1: Create the bot service**

Create `bot/src/services/get_my_servers_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

import httpx

import config
from config import API_URL
from exceptions import APIError
from services.handle_error import log_service_error


@dataclass(kw_only=True, slots=True, frozen=True)
class ServerItem:
    location: str
    proxy_link: str


@dataclass(kw_only=True, slots=True, frozen=True)
class MyServersResponse:
    expired_date: str
    servers: list[ServerItem]


@dataclass(kw_only=True, slots=True, frozen=True)
class GetMyServersService:
    url: str = API_URL + "/api/v1/users/my-servers/"

    @log_service_error
    async def __call__(self, *, telegram_id: str) -> MyServersResponse:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.url,
                data={"username": telegram_id},
                headers={"Bot-Auth-Token": config.BOT_AUTH_TOKEN},
            )
            response.raise_for_status()
            data = response.json()
            return MyServersResponse(
                expired_date=data["expired_date"],
                servers=[ServerItem(**item) for item in data["servers"]],
            )
```

- [ ] **Step 2: Export from bot services `__init__`**

In `bot/src/services/__init__.py`:

```python
from .first_moth_free import FirstMonthFreeService
from .check_first_month_free import CheckFirstMonthFreeService
from .referral_cabinet import GetReferralCabinetService
from .get_referral_link import GetReferralLinkService
from .get_product_service import GetInvoiceDataService
from .get_stars_invoice_data_service import GetStarsInvoiceDataService
from .buy_product_service import BuyProductService
from .update_link_service import UpdateUserKeyService
from .get_my_servers_service import GetMyServersService
```

- [ ] **Step 3: Commit**

```bash
git add bot/src/services/get_my_servers_service.py bot/src/services/__init__.py
git commit -m "feat(bot): add GetMyServersService HTTP client"
```

---

## Task 8: Bot handlers + messages

**Files:**
- Modify: `bot/src/messages.py`
- Modify: `bot/src/handlers.py`

- [ ] **Step 1: Update `messages.py`**

Replace the entire content of `bot/src/messages.py`:

```python
from enums import FreeAvailable

WELCOME_TEXT_MONTH = """
🚀 <b>Привет! Я помогу ускорить твой Telegram</b>

С MTPRoto твой Telegram будет летать даже при плохом интернете:
• 📱 Загрузка медиа за секунды
• 🎥 Видео без буферизации
• 🔒 Безопасное соединение
• ⚡️ Стабильная работа 24/7

<b>👇 Первый месяц — в подарок!</b>
"""

WELCOME_TEXT_WEEK = """
🚀 <b>Привет! Я помогу ускорить твой Telegram</b>

С MTPRoto твой Telegram будет летать даже при плохом интернете:
• 📱 Загрузка медиа за секунды
• 🎥 Видео без буферизации
• 🔒 Безопасное соединение
• ⚡️ Стабильная работа 24/7

<b>👇 Первая неделя — в подарок!</b>
"""

WELCOME_TEXT_TWO_WEEK = """
🚀 <b>Привет! Я помогу ускорить твой Telegram</b>

С MTPRoto твой Telegram будет летать даже при плохом интернете:
• 📱 Загрузка медиа за секунды
• 🎥 Видео без буферизации
• 🔒 Безопасное соединение
• ⚡️ Стабильная работа 24/7

👀 Вижу, что ты пришел по ссылке от друга!

<b>👇 Первые 2 недели — в подарок!</b>
"""


WELCOME_TEXT_NOT_FREE = """
🚀 <b>Привет! Я помогу ускорить твой Telegram</b>

С MTPRoto твой Telegram будет летать даже при плохом интернете:
• 📱 Загрузка медиа за секунды
• 🎥 Видео без буферизации
• 🔒 Безопасное соединение
• ⚡️ Стабильная работа 24/7

<b>👇 Жми «ускорить»!</b>
"""

FREE_AVAILABLE_TEXT_MAPPING = {
    FreeAvailable.MONTH: WELCOME_TEXT_MONTH,
    FreeAvailable.WEEK: WELCOME_TEXT_WEEK,
    FreeAvailable.TWO_WEEK: WELCOME_TEXT_TWO_WEEK,
    FreeAvailable.NOT_AVAILABLE: WELCOME_TEXT_NOT_FREE,
}


KEY_GENERATED_TEXT = """
🎉 <b>Твой персональный ключ готов!</b>

📝 <b>Как активировать:</b>
1. Нажми «Мои серверы» ниже
2. Подключи <b>все серверы</b> в Telegram — при падении одного он автоматически переключится на другой

⏳ Действительно до: <b>{expired_date}</b>

<i>🤝 Подпишись на наш канал — там все новости: @mtproto_keys</i>
"""

MY_SERVERS_TEXT = """
📡 <b>Твои серверы</b>

Подключи все серверы в Telegram — при отказе одного Telegram автоматически переключится на другой.

⏳ Ключ действителен до: <b>{expired_date}</b>

<i>👇 Нажми на каждый сервер чтобы добавить его</i>
"""

FAQ_TEXT = """
❓ <b>Часто задаваемые вопросы:</b>

<b>1. Это законно?</b>
✅ Да, MTPRoto — это легальный прокси-сервис, <b>встроенный</b> в эко-систему Telegram.

<b>2. А если не заработает?</b>
🛠 Мы даем бесплатную <b>неделю</b> на тест. Не понравится — просто не покупай.

<b>3. На сколько устройств хватит?</b>
📱 Один ключ работает на трех устройствах (для связки — телефон + ПК + планшет)

<b>4. Нужно ли что-то устанавливать?</b>
🔧 Нет, только вставить ключ в настройках Telegram

<b>5. Какая скорость?</b>
⚡️ Ограничений нет, только возможности твоего интернета

<b>6. Какие способы оплаты?</b>
💳 Банковская карта, SberPay, ЮMoney, ⭐ Telegram Stars

Остались вопросы? Напиши @mtproto_keys
"""

REFERRAL_CABINET = """
<b>⚡️Твой реферальный кабинет </b> 

• Общее количество инвайтов: <b>{total_referrals_count}</b>
• Активированные инвайты: <b>{active_referrals_count}</b>

🔗 Как только количество активированных инвайтов станет равно <b>5</b>, ты сможешь получить бесплатную ссылку <b>сроком действия 2 недели!</b>

👇 <b>Поделиться ссылкой</b>
"""
```

- [ ] **Step 2: Update `handlers.py`**

Replace the entire content of `bot/src/handlers.py`:

```python
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from messages import (
    FAQ_TEXT,
    FREE_AVAILABLE_TEXT_MAPPING,
    KEY_GENERATED_TEXT,
    MY_SERVERS_TEXT,
    REFERRAL_CABINET,
)
from services import (
    BuyProductService,
    CheckFirstMonthFreeService,
    FirstMonthFreeService,
    GetInvoiceDataService,
    GetMyServersService,
    GetStarsInvoiceDataService,
    GetReferralCabinetService,
    GetReferralLinkService,
    UpdateUserKeyService,
)

from src.bot import bot

router = Router()


def _build_main_menu_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder(
        markup=[
            [InlineKeyboardButton(text="⚡️ Ускорить Telegram", callback_data=callback_data)],
            [InlineKeyboardButton(text="📡 Мои серверы", callback_data="my_servers")],
            [InlineKeyboardButton(text="📋 Информация", callback_data="info")],
            [InlineKeyboardButton(text="🤝 Реферальный кабинет", callback_data="referral")],
        ],
    )
    return keyboard.adjust(1).as_markup()


def _build_my_servers_keyboard(servers) -> InlineKeyboardMarkup:
    keyboard = []
    for server in servers:
        keyboard.append([InlineKeyboardButton(text=server.location, url=server.proxy_link)])
    keyboard.append([InlineKeyboardButton(text="🔄 Перевыпустить ссылки", callback_data="update_link")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Command("start"))
async def cmd_start(message: Message):
    invited_from_username = None
    try:
        referrer_id = int(message.text.split()[-1])
        if referrer_id != message.from_user.id:
            invited_from_username = str(referrer_id)
    except ValueError:
        pass
    available_free_period = await CheckFirstMonthFreeService()(
        telegram_id=str(message.from_user.id),
        telegram_username=str(getattr(message.from_user, "username", None)),
        invited_from_username=invited_from_username,
    )
    text = FREE_AVAILABLE_TEXT_MAPPING.get(available_free_period)
    callback_data = "boost_free" if available_free_period != "NOT_AVAILABLE" else "boost_paid"
    await message.answer(
        text=text,
        reply_markup=_build_main_menu_keyboard(callback_data),
    )


@router.callback_query(F.data == "show_start_screen")
async def cmd_start_inline(callback: CallbackQuery):
    available_free_period = await CheckFirstMonthFreeService()(
        telegram_id=str(callback.message.chat.id),
        telegram_username=str(getattr(callback.message.from_user, "username", None)),
    )
    text = FREE_AVAILABLE_TEXT_MAPPING.get(available_free_period)
    callback_data = "boost_free" if available_free_period != "NOT_AVAILABLE" else "boost_paid"
    await callback.message.edit_text(
        text=text,
        reply_markup=_build_main_menu_keyboard(callback_data),
    )


@router.callback_query(F.data == "boost_free")
async def process_boost_free(callback: CallbackQuery):
    await callback.answer()
    response = await FirstMonthFreeService()(telegram_id=str(callback.message.chat.id))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📡 Мои серверы", callback_data="my_servers")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")],
    ])
    await callback.message.edit_text(
        text=KEY_GENERATED_TEXT.format(expired_date=response.expired_date),
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "my_servers")
async def process_my_servers(callback: CallbackQuery):
    await callback.answer()
    response = await GetMyServersService()(telegram_id=str(callback.message.chat.id))
    await callback.message.edit_text(
        text=MY_SERVERS_TEXT.format(expired_date=response.expired_date),
        reply_markup=_build_my_servers_keyboard(response.servers),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "info")
async def process_info(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        text=FAQ_TEXT,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👀 Договор-оферта",
                        url="https://drive.google.com/file/d/13GI1ZuKBm4nZkNxESOokGM6fTAAxaCs7/view?usp=sharing",
                    )
                ],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")],
            ]
        ),
    )


@router.callback_query(F.data == "referral")
async def process_referral(callback: CallbackQuery):
    await callback.answer()
    response = await GetReferralCabinetService()(
        telegram_id=str(callback.message.chat.id)
    )
    keyboard = []
    if response.active_referrals_count >= 5:
        keyboard.append(
            [InlineKeyboardButton(
                text="🎁 Получить бесплатную ссылку",
                callback_data="get-referral-link",
            )]
        )
    keyboard.append(
        [InlineKeyboardButton(
            text="🔗 Поделиться ссылкой",
            switch_inline_query=f"Привет! Переходи по моей реферальной ссылке: {response.referral_link}",
        )]
    )
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")])
    await callback.message.edit_text(
        text=REFERRAL_CABINET.format(
            total_referrals_count=response.total_referrals_count,
            active_referrals_count=response.active_referrals_count,
            referral_link=response.referral_link,
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


@router.callback_query(F.data == "get-referral-link")
async def process_referral_link(callback: CallbackQuery):
    await callback.answer()
    response = await GetReferralLinkService()(telegram_id=str(callback.message.chat.id))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📡 Мои серверы", callback_data="my_servers")],
    ])
    await callback.message.answer(
        text=KEY_GENERATED_TEXT.format(expired_date=response.expired_date),
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "boost_paid")
async def process_boost_paid(callback: CallbackQuery):
    await callback.answer()
    keyboard = InlineKeyboardBuilder(
        markup=[
            [InlineKeyboardButton(text="💳 ЮKassa — 79 ₽", callback_data="pay_yukassa")],
            [InlineKeyboardButton(text="⭐ Telegram Stars — 60 ★", callback_data="pay_stars")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")],
        ],
    )
    await callback.message.edit_text(
        text=(
            "💰 <b>Выберите способ оплаты</b>\n\n"
            "• 💳 <b>ЮKassa</b> — 79 ₽/месяц\n"
            "  Банковская карта, SberPay, ЮMoney\n\n"
            "• ⭐ <b>Telegram Stars</b> — 60 ★/месяц\n"
            "  Оплата прямо в Telegram\n"
        ),
        parse_mode="HTML",
        reply_markup=keyboard.adjust(1).as_markup(),
    )


@router.callback_query(F.data == "pay_yukassa")
async def process_pay_yukassa(callback: CallbackQuery):
    await callback.answer()
    response = await GetInvoiceDataService()()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        start_parameter="payment",
        payload="payment",
        **response.asdict(),
    )


@router.callback_query(F.data == "pay_stars")
async def process_pay_stars(callback: CallbackQuery):
    await callback.answer()
    response = await GetStarsInvoiceDataService()()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=response.title,
        description=response.description,
        start_parameter="payment_stars",
        payload="payment_stars",
        currency=response.currency,
        prices=response.prices,
        provider_token=response.provider_token,
    )


@router.callback_query(F.data == "update_link")
async def update_link(callback: CallbackQuery):
    await UpdateUserKeyService()(telegram_id=str(callback.message.chat.id))
    await callback.answer("✅ Ссылки обновлены!")
    response = await GetMyServersService()(telegram_id=str(callback.message.chat.id))
    await callback.message.edit_text(
        text=MY_SERVERS_TEXT.format(expired_date=response.expired_date),
        reply_markup=_build_my_servers_keyboard(response.servers),
        parse_mode="HTML",
    )


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    if message.successful_payment.currency == "XTR":
        charge_id = message.successful_payment.telegram_payment_charge_id
        provider = "stars"
    else:
        charge_id = message.successful_payment.provider_payment_charge_id
        provider = "yukassa"

    try:
        await BuyProductService()(
            telegram_id=message.from_user.id,
            charge_id=charge_id,
            provider=provider,
        )
    except Exception:
        await message.answer(
            "⚠️ Оплата получена, но произошла ошибка при выдаче ключа.\n"
            "Пожалуйста, обратитесь в поддержку: @mtproto_keys"
        )
```

- [ ] **Step 3: Run the Django test suite to make sure backend is clean**

```bash
make test
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add bot/src/handlers.py bot/src/messages.py
git commit -m "feat(bot): add Мои серверы screen, update main menu and key issuance handlers"
```

---

## Task 9: Django admin — update `proxy_purchased` template

This is a **manual data change** in Django admin. No code, no migration.

- [ ] **Step 1: Open Django admin**

Navigate to `/admin/notifications/notificationtemplate/` and find the template with `slug = proxy_purchased`.

- [ ] **Step 2: Update the template fields**

| Field | New value |
|-------|-----------|
| `button_text` | `📡 Мои серверы` |
| `button_url` | *(clear — leave empty)* |
| `button_callback_data` | `my_servers` |
| Template text | Remove any `{link}` references; use `{expired_date}` if the subscription end date should appear |

Example updated template text:
```
🎉 Оплата прошла! Твой ключ продлён.

⏳ Ключ действителен до: <b>{expired_date}</b>

👇 Нажми «Мои серверы» чтобы подключиться ко всем серверам
```

- [ ] **Step 3: Save and verify**

Open the bot, make a test payment (or use Stars sandbox), confirm the notification arrives with a "📡 Мои серверы" callback button.

---

## Self-Review Notes

- Task 1 covers `TestGetProxyLinkForServer` from spec ✓
- Task 2 covers `VDSInstance.location` migration ✓
- Task 3 covers `TestNotificationTemplateRender` callback_data cases ✓
- Task 4 covers `TestCreatePaymentService` context change ✓
- Task 5 covers `TestGetMyServersService` (all 5 cases) ✓
- Task 6 covers `TestMyServersView` (3 cases) + URL registration ✓
- Task 7 covers bot HTTP client ✓
- Task 8 covers all handler changes: main menu, `my_servers` handler, `boost_free`, `referral_link`, `update_link`, messages ✓
- Task 9 covers admin data change for `proxy_purchased` template ✓
