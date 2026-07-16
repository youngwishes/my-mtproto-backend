from __future__ import annotations

import hashlib
import json
import re
import unittest
import uuid
from pathlib import Path
from typing import Any

import yaml


CONTRACTS_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = CONTRACTS_DIR / "fixtures"
SCHEMA_PATH = CONTRACTS_DIR / "snapshot-v1.schema.json"
OPENAPI_PATH = CONTRACTS_DIR / "agent-v1.openapi.yaml"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _canonical_payload(snapshot: dict[str, Any]) -> bytes:
    payload = {
        "schema_version": snapshot["schema_version"],
        "snapshot_revision": snapshot["snapshot_revision"],
        "accesses": snapshot["accesses"],
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _validate_snapshot(snapshot: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if snapshot.get("schema_version") != schema["properties"]["schema_version"]["const"]:
        errors.append("incompatible schema major")

    accesses = snapshot.get("accesses", [])
    if len(accesses) > schema["properties"]["accesses"]["maxItems"]:
        errors.append("too many accesses")

    access_ids = [access.get("access_id") for access in accesses]
    if access_ids != sorted(access_ids) or len(access_ids) != len(set(access_ids)):
        errors.append("accesses are not uniquely sorted by numeric access_id")

    for access in accesses:
        if not isinstance(access.get("access_id"), int) or access["access_id"] < 1:
            errors.append("invalid access_id")
        if not isinstance(access.get("access_revision"), int) or access["access_revision"] < 1:
            errors.append("invalid access_revision")
        try:
            parsed_uuid = uuid.UUID(access.get("uuid", ""))
        except (ValueError, AttributeError):
            errors.append("invalid uuid")
        else:
            if str(parsed_uuid) != access["uuid"]:
                errors.append("uuid is not canonical")

    canonical = _canonical_payload(snapshot)
    if len(canonical) > schema["x-max-canonical-bytes"]:
        errors.append("canonical snapshot is too large")
    expected_hash = hashlib.sha256(canonical).hexdigest()
    if snapshot.get("snapshot_hash") != expected_hash:
        errors.append("snapshot hash mismatch")
    return errors


class AgentV1ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(SCHEMA_PATH.is_file(), f"missing contract schema: {SCHEMA_PATH}")
        self.assertTrue(OPENAPI_PATH.is_file(), f"missing OpenAPI contract: {OPENAPI_PATH}")
        self.schema = _load_json(SCHEMA_PATH)
        with OPENAPI_PATH.open(encoding="utf-8") as source:
            self.openapi = yaml.safe_load(source)

    def test_contract_exposes_only_exact_snapshot_endpoints(self) -> None:
        operations = {
            (method.upper(), path)
            for path, path_item in self.openapi["paths"].items()
            for method in path_item
            if method.lower() in {"get", "put", "post", "patch", "delete"}
        }
        self.assertEqual(
            operations,
            {
                ("GET", "/api/v1/health"),
                ("GET", "/api/v1/snapshot"),
                ("PUT", "/api/v1/snapshot"),
            },
        )

    def test_contract_constants_and_safe_response_matrix_are_stable(self) -> None:
        self.assertEqual(self.openapi["info"]["version"], "1.0.0")
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], "1.0")
        self.assertEqual(self.schema["properties"]["accesses"]["maxItems"], 5_000)
        self.assertEqual(self.schema["x-max-canonical-bytes"], 1_048_576)

        responses = self.openapi["paths"]["/api/v1/snapshot"]["put"]["responses"]
        expected_codes = {
            "409": {"stale_revision", "revision_conflict"},
            "413": {"snapshot_too_large"},
            "426": {"incompatible_contract"},
        }
        for status, error_codes in expected_codes.items():
            response_text = json.dumps(responses[status], sort_keys=True)
            for error_code in error_codes:
                self.assertIn(error_code, response_text)

    def test_canonical_fixtures_are_byte_deterministic(self) -> None:
        for fixture_name in ("canonical-empty.json", "canonical-two-accesses.json"):
            with self.subTest(fixture=fixture_name):
                snapshot = _load_json(FIXTURES_DIR / fixture_name)
                self.assertEqual(_validate_snapshot(snapshot, self.schema), [])
                canonical_path = FIXTURES_DIR / fixture_name.replace(".json", ".canonical.json")
                canonical_bytes = canonical_path.read_bytes()
                self.assertEqual(canonical_bytes, _canonical_payload(snapshot))
                self.assertFalse(canonical_bytes.startswith(b"\xef\xbb\xbf"))
                self.assertFalse(canonical_bytes.endswith(b"\n"))
                self.assertEqual(
                    snapshot["snapshot_hash"],
                    hashlib.sha256(canonical_bytes).hexdigest(),
                )

    def test_invalid_snapshot_fixtures_violate_contract(self) -> None:
        expected_error = {
            "invalid-unsorted.json": "accesses are not uniquely sorted by numeric access_id",
            "invalid-wrong-hash.json": "snapshot hash mismatch",
            "invalid-unknown-major.json": "incompatible schema major",
        }
        for fixture_name, error in expected_error.items():
            with self.subTest(fixture=fixture_name):
                snapshot = _load_json(FIXTURES_DIR / fixture_name)
                self.assertIn(error, _validate_snapshot(snapshot, self.schema))

    def test_equal_revision_with_different_hash_is_revision_conflict(self) -> None:
        current = _load_json(FIXTURES_DIR / "canonical-two-accesses.json")
        conflict = _load_json(FIXTURES_DIR / "invalid-revision-conflict.json")
        self.assertEqual(conflict["snapshot_revision"], current["snapshot_revision"])
        self.assertNotEqual(conflict["snapshot_hash"], current["snapshot_hash"])
        self.assertEqual(_validate_snapshot(conflict, self.schema), [])

        if conflict["snapshot_revision"] == current["snapshot_revision"]:
            decision = (
                "no_op"
                if conflict["snapshot_hash"] == current["snapshot_hash"]
                else "revision_conflict"
            )
        else:
            decision = "not_equal"
        self.assertEqual(decision, "revision_conflict")

    def test_openapi_has_no_incremental_mutation_endpoint(self) -> None:
        paths = "\n".join(self.openapi["paths"])
        self.assertIsNone(re.search(r"/(access|client)s?(?:/|$)", paths, re.IGNORECASE))
        prohibition = self.openapi["info"].get("description", "")
        self.assertIn("Incremental mutation endpoints are prohibited", prohibition)


if __name__ == "__main__":
    unittest.main()
