from __future__ import annotations

from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.vds import admin as vds_admin
from apps.vds.admin import MTPRotoKeyAdmin, VDSInstanceAdmin
from apps.vds.models import MTPRotoKey, VDSInstance
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class VDSAdminRegistrationTest(TestCase):
    def test_vds_admin_exposes_hosting_model_and_new_vds_fields(self) -> None:
        self.assertTrue(hasattr(vds_admin, "HostingAdmin"))
        self.assertIn("hosting", VDSInstanceAdmin.list_display)
        self.assertIn("expired_at", VDSInstanceAdmin.list_display)
        self.assertIn(VDSInstance, vds_admin.admin.site._registry)


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

        self.assertIn("nl1.mtprotokeys.com", html)
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
