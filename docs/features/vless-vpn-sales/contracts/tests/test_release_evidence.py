from __future__ import annotations

import re
import unittest
from pathlib import Path


CHECKLIST_PATH = Path(__file__).resolve().parents[2] / "release-checklist.md"


class ReleaseEvidenceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(CHECKLIST_PATH.is_file(), f"missing release checklist: {CHECKLIST_PATH}")
        self.checklist = CHECKLIST_PATH.read_text(encoding="utf-8")

    def test_release_evidence_has_all_immutable_compatibility_fields(self) -> None:
        required_fields = (
            "BACKEND_SHA",
            "AGENT_SHA",
            "CONTRACT_MAJOR",
            "SCHEMA_MAJOR",
            "XRAY_VERSION",
            "XRAY_IMAGE_DIGEST",
            "CONTRACT_TEST_RESULTS",
            "ROLLBACK_BACKEND_SHA",
            "ROLLBACK_AGENT_SHA",
        )
        for field in required_fields:
            with self.subTest(field=field):
                self.assertRegex(self.checklist, rf"(?m)^- `{field}=<[^>]+>`$")

    def test_release_order_is_agent_first_and_permission_is_explicit(self) -> None:
        ordered_gates = (
            "Agent PR and review",
            "Agent test deploy",
            "Backend integration and PR",
            "Controlled smoke",
            "Explicit production permission",
        )
        positions = [self.checklist.index(gate) for gate in ordered_gates]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("one exact compatible SHA pair", self.checklist)

    def test_backend_mutation_and_sales_have_hard_gates(self) -> None:
        self.assertIn(
            "MUST NOT send `PUT /api/v1/snapshot` before the agent SHA is reviewed and test-deployed",
            self.checklist,
        )
        self.assertIn(
            "MUST NOT enable VPN sales without a verified compatible backend/agent SHA pair",
            self.checklist,
        )

    def test_rollback_preserves_paid_receipts(self) -> None:
        self.assertIn(
            "A pre-VLESS backend is not a valid rollback target after the first accepted paid receipt",
            self.checklist,
        )
        self.assertRegex(
            self.checklist,
            re.compile(r"sales off.*paid receipt.*reconcile", re.IGNORECASE | re.DOTALL),
        )

    def test_tracked_evidence_template_contains_no_secret_or_ip_placeholders(self) -> None:
        forbidden = ("TOKEN=", "PASSWORD=", "PRIVATE_KEY=", "IP_ADDRESS=")
        for value in forbidden:
            self.assertNotIn(value, self.checklist)


if __name__ == "__main__":
    unittest.main()
