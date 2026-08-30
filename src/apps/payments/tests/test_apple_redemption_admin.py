from __future__ import annotations

from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase

from apps.payments import admin as payments_admin
from apps.payments.models import AppleRedemption


class TestAppleRedemptionAdmin(SimpleTestCase):
    def test_redemption_admin_is_registered_as_read_only_journal(self) -> None:
        self.assertIn(AppleRedemption, admin.site._registry)
        model_admin = admin.site._registry[AppleRedemption]
        request = RequestFactory().get("/admin/payments/appleredemption/")

        self.assertIsInstance(model_admin, payments_admin.AppleRedemptionAdmin)
        self.assertIsNone(model_admin.actions)
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertEqual(
            model_admin.get_readonly_fields(request),
            tuple(field.name for field in AppleRedemption._meta.fields),
        )
        self.assertEqual(
            model_admin.list_display,
            (
                "id",
                "user",
                "key",
                "apples_spent",
                "days",
                "new_expired_at",
                "balance_after",
                "created_at",
            ),
        )
        self.assertEqual(model_admin.list_filter, ("new_expired_at",))
        self.assertEqual(
            model_admin.search_fields,
            ("user__username", "user__telegram_username", "key__token"),
        )
        self.assertEqual(model_admin.days(AppleRedemption(apples_spent=30)), 2)
