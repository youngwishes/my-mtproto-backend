from __future__ import annotations

from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.vds.admin import MTPRotoKeyAdmin
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class MTPRotoKeyAdminProxyLinkTest(TestCase):
    def setUp(self) -> None:
        self.admin = MTPRotoKeyAdmin(MTPRotoKey, AdminSite())
        self.request = RequestFactory().get("/admin/vds/mtprotokey/")

    def _prime_example_server(self) -> None:
        # get_queryset stashes the example server name used for every row
        self.admin.get_queryset(self.request)

    def test_link_uses_example_active_server(self) -> None:
        VDSInstanceFactory(name="nl1")
        key = MTPRotoKeyFactory(expired_date=timezone.now() + timedelta(days=5))
        self._prime_example_server()

        html = self.admin.active_proxy_link(key)

        self.assertIn("nl1.beatvault.ru", html)
        self.assertIn(key.get_secret_token(), html)

    def test_dash_when_key_is_not_valid(self) -> None:
        VDSInstanceFactory(name="nl1")
        key = MTPRotoKeyFactory(
            was_deleted=True, expired_date=timezone.now() + timedelta(days=5)
        )
        self._prime_example_server()

        self.assertEqual(self.admin.active_proxy_link(key), "—")

    def test_dash_when_no_active_server(self) -> None:
        key = MTPRotoKeyFactory(expired_date=timezone.now() + timedelta(days=5))
        self._prime_example_server()

        self.assertEqual(self.admin.active_proxy_link(key), "—")
