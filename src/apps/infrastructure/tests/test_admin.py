from __future__ import annotations

from django.contrib import admin
from django.test import SimpleTestCase

from apps.infrastructure.admin import ProjectServerAdmin
from apps.infrastructure.models import ProjectServer


class ProjectServerAdminTest(SimpleTestCase):
    def test_model_is_registered_with_the_approved_admin_class(self) -> None:
        registered_admin = admin.site._registry[ProjectServer]

        self.assertIsInstance(registered_admin, ProjectServerAdmin)

    def test_changelist_configuration_matches_the_approved_contract(self) -> None:
        self.assertEqual(
            ProjectServerAdmin.list_display,
            (
                "ipv4",
                "hosting",
                "price",
                "currency",
                "next_payment_date",
                "description",
                "is_active",
            ),
        )
        self.assertEqual(ProjectServerAdmin.ordering, ("next_payment_date", "ipv4"))
        self.assertEqual(ProjectServerAdmin.list_select_related, ("hosting",))
        self.assertEqual(
            ProjectServerAdmin.search_fields,
            ("ipv4", "hosting__name", "description"),
        )
        self.assertEqual(
            ProjectServerAdmin.list_filter,
            ("is_active", "hosting", "currency"),
        )
        self.assertEqual(
            ProjectServerAdmin.list_editable,
            ("price", "currency", "next_payment_date", "is_active"),
        )
