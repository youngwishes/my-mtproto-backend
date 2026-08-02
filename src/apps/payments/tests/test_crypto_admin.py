from __future__ import annotations

from django.contrib import admin
from django.test import RequestFactory, TestCase

from apps.payments.admin import CryptoPaymentIntentAdmin
from apps.payments.models import CryptoPaymentIntent


class TestCryptoPaymentIntentAdmin(TestCase):
    def test_crypto_admin_has_no_write_surface(self) -> None:
        model_admin = CryptoPaymentIntentAdmin(CryptoPaymentIntent, admin.site)
        request = RequestFactory().get("/admin/payments/cryptopaymentintent/")

        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertEqual(model_admin.actions, None)
        self.assertEqual(
            set(model_admin.get_readonly_fields(request)),
            {field.name for field in CryptoPaymentIntent._meta.fields},
        )
