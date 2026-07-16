from __future__ import annotations

import ast
from pathlib import Path

from django.test import SimpleTestCase


class PaymentImportGraphTest(SimpleTestCase):
    def test_payments_package_does_not_import_vpn_or_own_concrete_consumer(
        self,
    ) -> None:
        payments_root = Path(__file__).resolve().parents[1]
        violations: list[str] = []
        for path in payments_root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                if any(
                    name == "apps.vpn" or name.startswith("apps.vpn.") for name in names
                ):
                    violations.append(str(path.relative_to(payments_root)))
        self.assertEqual(violations, [])
        tasks_path = payments_root / "tasks.py"
        if tasks_path.exists():
            self.assertNotIn("payment_receipt", tasks_path.read_text())
