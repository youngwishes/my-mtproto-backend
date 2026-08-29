from __future__ import annotations

from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.fortune_wheel.admin import FortuneSpinAdmin
from apps.fortune_wheel.models import FortuneSpin
from apps.fortune_wheel.tests.factories import FortuneSpinFactory
from apps.users.tests.factories import SystemUserFactory


class FortuneSpinAdminTest(TestCase):
    def setUp(self) -> None:
        self.admin = FortuneSpinAdmin(FortuneSpin, AdminSite())
        self.request = RequestFactory().get("/admin/fortune-wheel/")
        self.request.user = SystemUserFactory(is_staff=True, is_superuser=True)

    def test_existing_spin_can_be_changed_but_not_added_or_deleted(self) -> None:
        self.assertFalse(self.admin.has_add_permission(self.request))
        self.assertTrue(self.admin.has_change_permission(self.request))
        self.assertFalse(self.admin.has_delete_permission(self.request))
        self.assertEqual(
            self.admin.get_readonly_fields(self.request),
            ("id", "updated_at"),
        )

    def test_change_form_updates_all_working_fields_without_adjusting_balances(
        self,
    ) -> None:
        original_user = SystemUserFactory(apple_balance=100)
        replacement_user = SystemUserFactory(apple_balance=200)
        spin = FortuneSpinFactory(user=original_user, prize_apples=15)
        created_at = timezone.now().replace(microsecond=0) - timedelta(days=3)

        form_class = self.admin.get_form(self.request, spin)
        form = form_class(
            data={
                "user": replacement_user.pk,
                "prize_apples": 60,
                "created_at_0": created_at.strftime("%Y-%m-%d"),
                "created_at_1": created_at.strftime("%H:%M:%S"),
            },
            instance=spin,
        )

        self.assertEqual(
            tuple(form.fields),
            ("is_active", "created_at", "user", "prize_apples"),
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        spin.refresh_from_db()
        original_user.refresh_from_db()
        replacement_user.refresh_from_db()
        self.assertEqual(spin.user, replacement_user)
        self.assertEqual(spin.prize_apples, 60)
        self.assertFalse(spin.is_active)
        self.assertEqual(spin.created_at, created_at)
        self.assertEqual(original_user.apple_balance, 100)
        self.assertEqual(replacement_user.apple_balance, 200)

    def test_change_form_preserves_existing_created_at_as_initial_value(self) -> None:
        spin = FortuneSpinFactory()

        form_class = self.admin.get_form(self.request, spin)
        form = form_class(instance=spin)

        self.assertEqual(form.initial.get("created_at"), spin.created_at)
