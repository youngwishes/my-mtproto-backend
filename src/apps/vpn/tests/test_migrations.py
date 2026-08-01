from __future__ import annotations

from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase


class TestVPNMigrationPackage(SimpleTestCase):
    def test_initial_migration_is_discoverable(self) -> None:
        loader = MigrationLoader(None, load=False)
        loader.load_disk()

        self.assertIn(("vpn", "0001_initial"), loader.disk_migrations)
