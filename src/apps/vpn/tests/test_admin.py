from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpRequest
from django.template.response import TemplateResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.payments.tests.factories import PaymentFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vpn.admin import (
    VPNAccessAdmin,
    VPNNodeAdmin,
    VPNNodeAdminForm,
    VPNPurchaseAdmin,
)
from apps.vpn.exceptions import VPNRefundConflict
from apps.vpn.models import VPNAccess, VPNAccessNodeApply, VPNNode, VPNPurchase
from apps.vpn.services.deactivate_refund import DeactivateVPNRefundService
from apps.vpn.tests.factories import VPNAccessFactory, VPNNodeFactory


class VPNAdminTests(TestCase):
    def _request(
        self,
        *,
        confirmed: bool = False,
        confirmation_token: str = "",
    ) -> HttpRequest:
        data = {"confirm": "yes"} if confirmed else {}
        if confirmation_token:
            data["confirmation_token"] = confirmation_token
        request = RequestFactory().post("/admin/vpn/vpnpurchase/", data=data)
        request.user = SystemUserFactory(is_staff=True, is_superuser=True)
        request.session = self.client.session
        request._messages = FallbackStorage(request)
        return request

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

    def test_refund_action_belongs_to_purchase_not_access(self) -> None:
        access_admin = VPNAccessAdmin(VPNAccess, AdminSite())
        purchase_admin = VPNPurchaseAdmin(VPNPurchase, AdminSite())

        self.assertNotIn("deactivate_after_refund", access_admin.actions)
        self.assertIn("deactivate_after_refund", purchase_admin.actions)

    def test_refund_action_requires_one_purchase_and_explicit_confirmation(
        self,
    ) -> None:
        access = VPNAccessFactory()
        payment = PaymentFactory(
            user=access.user, charge_id="provider-charge-123456789"
        )
        purchase = VPNPurchase.objects.create(
            payment=payment,
            access=access,
            expired_at_after=access.expired_at,
        )
        model_admin = VPNPurchaseAdmin(VPNPurchase, AdminSite())

        response = model_admin.deactivate_after_refund(
            self._request(),
            VPNPurchase.objects.filter(pk=purchase.pk),
        )

        self.assertIsInstance(response, TemplateResponse)
        self.assertEqual(
            response.template_name,
            "admin/vpn/vpnpurchase/refund_confirmation.html",
        )
        self.assertEqual(response.context_data["purchase"], purchase)
        self.assertEqual(response.context_data["safe_payment_identity"], "••••••")
        rendered = response.render().content.decode()
        self.assertIn("••••••", rendered)
        self.assertNotIn(payment.charge_id, rendered)
        access.refresh_from_db()
        self.assertNotEqual(access.state, "disabled_refund")

        refund_service = DeactivateVPNRefundService(schedule_reconcile=Mock())
        with patch(
            "apps.vpn.admin.get_deactivate_vpn_refund_service",
            return_value=refund_service,
        ):
            model_admin.deactivate_after_refund(
                self._request(
                    confirmed=True,
                    confirmation_token=response.context_data["confirmation_token"],
                ),
                VPNPurchase.objects.filter(pk=purchase.pk),
            )
        access.refresh_from_db()
        purchase.refresh_from_db()
        self.assertEqual(access.state, "disabled_refund")
        self.assertIsNotNone(purchase.refunded_at)

    def test_refund_confirmation_rejects_multiple_selected_purchases(self) -> None:
        first_access = VPNAccessFactory()
        second_access = VPNAccessFactory()
        purchases = []
        for access in (first_access, second_access):
            purchases.append(
                VPNPurchase.objects.create(
                    payment=PaymentFactory(user=access.user),
                    access=access,
                    expired_at_after=timezone.now(),
                )
            )
        model_admin = VPNPurchaseAdmin(VPNPurchase, AdminSite())

        response = model_admin.deactivate_after_refund(
            self._request(),
            VPNPurchase.objects.filter(pk__in=[purchase.pk for purchase in purchases]),
        )

        self.assertIsNone(response)
        self.assertFalse(VPNPurchase.objects.filter(refunded_at__isnull=False).exists())

    def test_refund_confirmation_token_rejects_changed_selection(self) -> None:
        original_access = VPNAccessFactory()
        changed_access = VPNAccessFactory()
        original = VPNPurchase.objects.create(
            payment=PaymentFactory(user=original_access.user),
            access=original_access,
            expired_at_after=original_access.expired_at,
        )
        changed = VPNPurchase.objects.create(
            payment=PaymentFactory(user=changed_access.user),
            access=changed_access,
            expired_at_after=changed_access.expired_at,
        )
        model_admin = VPNPurchaseAdmin(VPNPurchase, AdminSite())
        confirmation = model_admin.deactivate_after_refund(
            self._request(),
            VPNPurchase.objects.filter(pk=original.pk),
        )

        response = model_admin.deactivate_after_refund(
            self._request(
                confirmed=True,
                confirmation_token=confirmation.context_data["confirmation_token"],
            ),
            VPNPurchase.objects.filter(pk=changed.pk),
        )

        self.assertIsNone(response)
        original.refresh_from_db()
        changed.refresh_from_db()
        self.assertIsNone(original.refunded_at)
        self.assertIsNone(changed.refunded_at)

    def test_payment_identity_never_contains_short_empty_or_long_charge_id(
        self,
    ) -> None:
        model_admin = VPNPurchaseAdmin(VPNPurchase, AdminSite())
        for charge_id in (
            "",
            "a",
            "ab",
            "abc",
            "abcd",
            "abcde",
            "abcdef",
            "abcdefg",
            "provider-charge-123456789",
        ):
            with self.subTest(charge_id=charge_id):
                access = VPNAccessFactory()
                purchase = VPNPurchase.objects.create(
                    payment=PaymentFactory(user=access.user, charge_id=charge_id),
                    access=access,
                    expired_at_after=access.expired_at,
                )

                masked = model_admin.safe_payment_identity(purchase)

                self.assertEqual(masked, "••••••")
                if charge_id:
                    self.assertNotIn(charge_id, masked)

    def test_refund_conflict_displays_bounded_safe_message(self) -> None:
        access = VPNAccessFactory()
        purchase = VPNPurchase.objects.create(
            payment=PaymentFactory(user=access.user),
            access=access,
            expired_at_after=access.expired_at,
        )
        model_admin = VPNPurchaseAdmin(VPNPurchase, AdminSite())
        confirmation = model_admin.deactivate_after_refund(
            self._request(),
            VPNPurchase.objects.filter(pk=purchase.pk),
        )
        request = self._request(
            confirmed=True,
            confirmation_token=confirmation.context_data["confirmation_token"],
        )
        failing_service = Mock(side_effect=VPNRefundConflict())

        with patch(
            "apps.vpn.admin.get_deactivate_vpn_refund_service",
            return_value=failing_service,
        ):
            model_admin.deactivate_after_refund(
                request,
                VPNPurchase.objects.filter(pk=purchase.pk),
            )

        visible_messages = [str(message) for message in request._messages]
        self.assertEqual(
            visible_messages,
            ["Состояние VPN изменилось, повторите проверку возврата"],
        )
        self.assertNotIn("database", visible_messages[0].lower())

    def test_refund_confirmation_rejects_active_renewal_without_calling_service(
        self,
    ) -> None:
        access = VPNAccessFactory()
        original = VPNPurchase.objects.create(
            payment=PaymentFactory(user=access.user),
            access=access,
            expired_at_after=access.expired_at,
        )
        model_admin = VPNPurchaseAdmin(VPNPurchase, AdminSite())
        confirmation = model_admin.deactivate_after_refund(
            self._request(),
            VPNPurchase.objects.filter(pk=original.pk),
        )
        original_revision = access.state_revision
        access.expired_at += timedelta(days=30)
        access.save(update_fields=("expired_at", "updated_at"))
        VPNPurchase.objects.create(
            payment=PaymentFactory(user=access.user),
            access=access,
            expired_at_after=access.expired_at,
        )

        factory = Mock()
        with patch("apps.vpn.admin.get_deactivate_vpn_refund_service", factory):
            response = model_admin.deactivate_after_refund(
                self._request(
                    confirmed=True,
                    confirmation_token=confirmation.context_data["confirmation_token"],
                ),
                VPNPurchase.objects.filter(pk=original.pk),
            )

        self.assertIsNone(response)
        factory.assert_not_called()
        access.refresh_from_db()
        original.refresh_from_db()
        self.assertEqual(access.state_revision, original_revision)
        self.assertNotEqual(access.state, "disabled_refund")
        self.assertIsNone(original.refunded_at)

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
