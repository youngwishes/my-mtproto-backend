from __future__ import annotations

from django.contrib import admin
from django.test import RequestFactory, TestCase

from apps.payments.admin import PaymentMethodAdmin
from apps.payments.models import PaymentMethod


class TestPaymentMethodAdmin(TestCase):
    def test_payment_method_admin_exposes_priority_with_existing_restrictions(self) -> None:
        model_admin = PaymentMethodAdmin(PaymentMethod, admin.site)
        request = RequestFactory().get("/admin/payments/paymentmethod/")

        self.assertEqual(
            model_admin.list_display,
            (
                "code",
                "commission_percent",
                "is_active",
                "is_priority",
                "updated_at",
            ),
        )
        self.assertEqual(
            model_admin.list_editable,
            ("commission_percent", "is_active", "is_priority"),
        )
        self.assertEqual(
            model_admin.readonly_fields,
            ("code", "created_at", "updated_at"),
        )
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertIsNone(model_admin.actions)
        self.assertIs(
            admin.site._registry[PaymentMethod].__class__, PaymentMethodAdmin
        )
