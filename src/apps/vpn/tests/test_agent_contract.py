from __future__ import annotations

import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from apps.vpn.dtos import VPNExactSnapshotDTO
from apps.vpn.services.build_snapshot import (
    SNAPSHOT_V1_MAX_CANONICAL_BYTES,
    SNAPSHOT_V1_MAX_ENTRIES,
    SNAPSHOT_V1_SCHEMA_VERSION,
)


CONTRACT_DIR = (
    Path(__file__).parents[4] / "docs/features/vless-vpn-sales/contracts"
)


class VPNAgentConsumerContractTests(SimpleTestCase):
    def test_backend_gate_matches_reviewed_a010_runtime_evidence(self) -> None:
        evidence = json.loads(
            (Path(__file__).with_name("fixtures") / "agent-a010-runtime.json").read_text()
        )

        self.assertEqual(settings.VPN_AGENT_EXPECTED_SHA, evidence["agent_sha"])
        self.assertEqual(
            settings.VPN_AGENT_EXPECTED_XRAY_VERSION,
            evidence["xray_version"],
        )
        self.assertEqual(
            settings.VPN_AGENT_EXPECTED_XRAY_IMAGE_DIGEST,
            evidence["xray_image_digest"],
        )

    def test_consumer_limits_are_sourced_from_contract_v1(self) -> None:
        schema = json.loads((CONTRACT_DIR / "snapshot-v1.schema.json").read_text())

        self.assertEqual(
            SNAPSHOT_V1_SCHEMA_VERSION,
            schema["properties"]["schema_version"]["const"],
        )
        self.assertEqual(
            SNAPSHOT_V1_MAX_ENTRIES,
            schema["properties"]["accesses"]["maxItems"],
        )
        self.assertEqual(
            SNAPSHOT_V1_MAX_CANONICAL_BYTES,
            schema["x-max-canonical-bytes"],
        )

    def test_consumer_round_trips_exact_canonical_fixtures(self) -> None:
        fixture_dir = CONTRACT_DIR / "fixtures"
        for name in ("canonical-empty", "canonical-two-accesses"):
            with self.subTest(name=name):
                payload = json.loads((fixture_dir / f"{name}.json").read_text())
                canonical = (fixture_dir / f"{name}.canonical.json").read_bytes()
                snapshot = VPNExactSnapshotDTO.from_payload(payload)

                self.assertEqual(snapshot.as_payload(), payload)
                self.assertEqual(snapshot.canonical_bytes, canonical)
                self.assertEqual(
                    snapshot.snapshot_hash,
                    hashlib.sha256(canonical).hexdigest(),
                )

    def test_consumer_rejects_invalid_shared_fixtures(self) -> None:
        fixture_dir = CONTRACT_DIR / "fixtures"
        for name in (
            "invalid-unsorted.json",
            "invalid-wrong-hash.json",
            "invalid-unknown-major.json",
        ):
            with self.subTest(name=name):
                payload = json.loads((fixture_dir / name).read_text())
                with self.assertRaises(ValueError):
                    VPNExactSnapshotDTO.from_payload(payload)
