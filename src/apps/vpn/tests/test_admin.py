from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from apps.vpn.admin import VPNAccessAdmin, VPNNodeAdmin, VPNNodeAdminForm
from apps.vpn.models import VPNAccess, VPNAccessNodeApply, VPNNode, VPNPurchase
from apps.vpn.tests.factories import VPNAccessFactory, VPNNodeFactory


class VPNAdminTests(TestCase):
    def test_all_models_are_registered(self) -> None:
        for model in (VPNAccess, VPNPurchase, VPNNode, VPNAccessNodeApply):
            self.assertIn(model, admin.site._registry)

    def test_access_admin_masks_token_and_never_exposes_raw_field(self) -> None:
        access = VPNAccessFactory(subscription_token="a" * 43)
        model_admin = VPNAccessAdmin(VPNAccess, AdminSite())

        self.assertNotIn("subscription_token", model_admin.get_fields(None, access))
        masked = model_admin.masked_subscription_token(access)
        self.assertNotEqual(masked, access.subscription_token)
        self.assertEqual(masked, "aaaaaa…aaaa")

    def test_node_admin_form_rejects_private_key_and_target(self) -> None:
        node = VPNNodeFactory.build()
        data = {
            field.name: getattr(node, field.name)
            for field in VPNNode._meta.fields
            if field.editable and field.name not in {"id", "created_at", "updated_at"}
        }
        data["reality_private_key"] = "forbidden"
        data["reality_target"] = "www.example.com:443"

        form = VPNNodeAdminForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("Приватный REALITY key", form.non_field_errors()[0])

    def test_node_admin_uses_protective_form(self) -> None:
        self.assertIs(VPNNodeAdmin.form, VPNNodeAdminForm)
