from __future__ import annotations

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from apps.fortune_wheel.admin import FortuneSpinAdmin
from apps.fortune_wheel.models import FortuneSpin
from apps.users.tests.factories import SystemUserFactory


class FortuneSpinAdminTest(TestCase):
    def test_spin_history_is_read_only(self) -> None:
        admin = FortuneSpinAdmin(FortuneSpin, AdminSite())
        request = RequestFactory().get("/admin/fortune-wheel/")
        request.user = SystemUserFactory(is_staff=True, is_superuser=True)

        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request))
        self.assertFalse(admin.has_delete_permission(request))
        self.assertEqual(
            admin.get_readonly_fields(request),
            ("id", "is_active", "created_at", "updated_at", "user", "prize_apples"),
        )
