from __future__ import annotations

from django.contrib import admin
from django.test import RequestFactory, TestCase

from apps.payments.admin import PlategaPaymentIntentAdmin
from apps.payments.models import PlategaPaymentIntent


class TestPlategaPaymentIntentAdmin(TestCase):
    def test_intent_admin_is_registered_read_only_diagnostics(self) -> None:
        model_admin = PlategaPaymentIntentAdmin(PlategaPaymentIntent, admin.site)
        request = RequestFactory().get("/admin/payments/plategapaymentintent/")

        self.assertIsNone(model_admin.actions)
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertEqual(
            model_admin.get_readonly_fields(request),
            tuple(field.name for field in PlategaPaymentIntent._meta.fields),
        )
        self.assertIs(
            admin.site._registry[PlategaPaymentIntent].__class__,
            PlategaPaymentIntentAdmin,
        )
