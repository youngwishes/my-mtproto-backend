from __future__ import annotations

from django.apps import apps as django_apps
from django.conf import settings
from django.test import SimpleTestCase

import apps.infrastructure as infrastructure_package
from apps.infrastructure.apps import InfrastructureConfig


class InfrastructureAppConfigTest(SimpleTestCase):
    def test_application_is_registered_with_the_approved_config(self) -> None:
        app_config = django_apps.get_app_config("infrastructure")

        self.assertIsInstance(app_config, InfrastructureConfig)
        self.assertEqual(InfrastructureConfig.name, "apps.infrastructure")
        self.assertIn("apps.infrastructure", settings.INSTALLED_APPS)

    def test_top_level_package_exports_nothing(self) -> None:
        self.assertEqual(infrastructure_package.__all__, [])
