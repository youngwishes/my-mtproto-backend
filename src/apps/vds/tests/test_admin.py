from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

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
        self.assertIn("tls_domain", VDSInstanceAdmin.list_display)
        self.assertIn(VDSInstance, vds_admin.admin.site._registry)


class VDSInstanceAdminFormTest(TestCase):
    def setUp(self) -> None:
        self.admin = VDSInstanceAdmin(VDSInstance, AdminSite())
        self.request = RequestFactory().get("/admin/vds/vdsinstance/add/")

    def _form_data(self, *, tls_domain: str) -> dict[str, str]:
        return {
            "name": "nl1",
            "tls_domain": tls_domain,
            "number": "1",
            "ip_address": "192.0.2.1",
            "internal_ip_address": "192.0.2.2",
            "port": "8000",
            "location": "NL",
        }

    def test_empty_tls_domain_is_invalid(self) -> None:
        form_class = self.admin.get_form(self.request)

        form = form_class(data=self._form_data(tls_domain=""))

        self.assertFalse(form.is_valid())
        self.assertIn("tls_domain", form.errors)

    def test_duplicate_tls_domain_is_valid_without_dns_lookup(self) -> None:
        VDSInstanceFactory(tls_domain="shared.example")
        form_class = self.admin.get_form(self.request)

        with patch("socket.getaddrinfo") as dns_lookup:
            form = form_class(data=self._form_data(tls_domain="shared.example"))

            self.assertTrue(form.is_valid(), form.errors)
            dns_lookup.assert_not_called()


class MTPRotoKeyAdminProxyLinkTest(TestCase):
    def setUp(self) -> None:
        self.admin = MTPRotoKeyAdmin(MTPRotoKey, AdminSite())
        self.request = RequestFactory().get("/admin/vds/mtprotokey/")

    def _prime_example_server(self) -> None:
        # get_queryset stashes the example server used for every row
        self.admin.get_queryset(self.request)

    def test_link_uses_example_active_server(self) -> None:
        vds = VDSInstanceFactory(name="nl1", tls_domain="tls-preview.example")
        key = MTPRotoKeyFactory(expired_date=timezone.now() + timedelta(days=5))
        self._prime_example_server()

        html = self.admin.active_proxy_link(key)

        self.assertIn("nl1.mtprotokeys.com", html)
        self.assertIn(key.get_secret_token(tls_domain=vds.tls_domain), html)

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
