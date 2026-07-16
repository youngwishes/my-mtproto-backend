from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from django.core.management import BaseCommand, CommandError
from django.db import connection

from apps.payments.selectors import (
    get_duplicate_non_empty_payment_identity_count,
    get_product_preflight_rows,
)

_MINIMUM_MIGRATION_HEADROOM_BYTES = 8 * 1024 * 1024
_REQUIRED_BACKUP_TABLES = frozenset(
    {
        "django_migrations",
        "payments_product",
        "payments_payment",
        "payments_giftcertificate",
    }
)


class Command(BaseCommand):
    """Validate rollback-safe VLESS migration prerequisites without DB writes."""

    help = "Run the read-only preflight for the VLESS expand migrations."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--backup-path",
            required=True,
            help="Path to a restored SQLite backup copy to validate.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        failures: list[str] = []
        products = get_product_preflight_rows()
        active_products = [product for product in products if product[2]]
        if len(active_products) != 1:
            failures.append("expected exactly one active Product")
            self.stdout.write("Product inventory (safe fields only):")
            for product_pk, code, is_active in products:
                safe_code = code or "<unset>"
                status = "active" if is_active else "inactive"
                self.stdout.write(
                    f"  pk={product_pk} code={safe_code} status={status}"
                )

        duplicate_count = get_duplicate_non_empty_payment_identity_count()
        if duplicate_count:
            failures.append("duplicate non-empty payment identities")
            self.stdout.write(f"Duplicate payment identity groups: {duplicate_count}")

        orphan_rows = self._get_orphan_rows()
        if orphan_rows:
            failures.append("orphan relations")
            self.stdout.write("Orphan relations (safe fields only):")
            for table_name, row_id, _parent, _fk_index in orphan_rows:
                self.stdout.write(f"  table={table_name} pk={row_id}")

        backup_path = Path(options["backup_path"])
        if not self._is_valid_sqlite_backup(backup_path=backup_path):
            failures.append("SQLite backup is not prepared")

        required_free_bytes = max(
            self._get_database_size_bytes() * 2,
            _MINIMUM_MIGRATION_HEADROOM_BYTES,
        )
        database_directory = self._get_database_directory()
        if shutil.disk_usage(database_directory).free < required_free_bytes:
            failures.append("insufficient free space for SQLite table rebuild")

        if failures:
            raise CommandError("VLESS migration preflight failed: " + "; ".join(failures))

        self.stdout.write(self.style.SUCCESS("VLESS migration preflight passed"))

    def _get_orphan_rows(self) -> list[tuple[str, int | None, str, int]]:
        if connection.vendor != "sqlite":
            raise CommandError("VLESS migration preflight requires SQLite")
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_key_check")
            return list(cursor.fetchall())

    def _is_valid_sqlite_backup(self, *, backup_path: Path) -> bool:
        resolved_backup_path = backup_path.expanduser().resolve(strict=False)
        live_database_path = self._get_live_database_path()
        if live_database_path is not None and (
            resolved_backup_path == live_database_path
            or self._paths_reference_same_file(
                first=resolved_backup_path,
                second=live_database_path,
            )
        ):
            return False
        if (
            not resolved_backup_path.is_file()
            or resolved_backup_path.stat().st_size == 0
        ):
            return False
        try:
            with sqlite3.connect(
                f"{resolved_backup_path.as_uri()}?mode=ro",
                uri=True,
            ) as backup:
                result = backup.execute("PRAGMA integrity_check").fetchone()
                orphan_relation = backup.execute(
                    "PRAGMA foreign_key_check"
                ).fetchone()
                tables = {
                    row[0]
                    for row in backup.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
        except (OSError, sqlite3.DatabaseError):
            return False
        return (
            result == ("ok",)
            and orphan_relation is None
            and _REQUIRED_BACKUP_TABLES <= tables
        )

    def _get_live_database_path(self) -> Path | None:
        database_name = str(connection.settings_dict["NAME"])
        if database_name == ":memory:":
            return None
        if database_name.startswith("file:"):
            parsed_name = urlsplit(database_name)
            if parse_qs(parsed_name.query).get("mode") == ["memory"]:
                return None
            if not parsed_name.path:
                return None
            database_path = Path(unquote(parsed_name.path))
        else:
            database_path = Path(database_name)
        return database_path.expanduser().resolve(strict=False)

    def _paths_reference_same_file(self, *, first: Path, second: Path) -> bool:
        try:
            return first.samefile(second)
        except (FileNotFoundError, OSError):
            return False

    def _get_database_size_bytes(self) -> int:
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA page_count")
            page_count = int(cursor.fetchone()[0])
            cursor.execute("PRAGMA page_size")
            page_size = int(cursor.fetchone()[0])
        return page_count * page_size

    def _get_database_directory(self) -> Path:
        database_name = str(connection.settings_dict["NAME"])
        if database_name.startswith("file:"):
            return Path.cwd()
        return Path(database_name).resolve().parent
