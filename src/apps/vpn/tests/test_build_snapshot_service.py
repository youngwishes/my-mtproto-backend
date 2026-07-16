from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path
from uuid import UUID

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vpn.dtos import VPNDesiredAccessDTO
from apps.vpn.enums import VPNAccessState
from apps.vpn.selectors import get_desired_vpn_snapshot_accesses
from apps.vpn.services import (
    BuildVPNSnapshotService,
    ForecastVPNSnapshotCapacityService,
    get_build_vpn_snapshot_service,
    get_forecast_vpn_snapshot_capacity_service,
)
from apps.vpn.tests.factories import VPNAccessFactory


CONTRACT_FIXTURES = (
    Path(__file__).parents[4]
    / "docs/features/vless-vpn-sales/contracts/fixtures"
)


def _access(
    access_id: int,
    uuid: str,
    revision: int,
    *,
    customer_id: int | None = None,
) -> VPNDesiredAccessDTO:
    return VPNDesiredAccessDTO(
        access_id=access_id,
        uuid=UUID(uuid),
        access_revision=revision,
        customer_id=customer_id,
    )


class BuildVPNSnapshotServiceTests(TestCase):
    def test_matches_shared_agent_fixture_byte_for_byte(self) -> None:
        accesses = (
            _access(10, "2f1c5a63-7bd6-4ac1-86dc-16b7adf580df", 3),
            _access(2, "01890f47-a2d4-7c11-b3e6-89f40d8639f1", 1),
        )
        service = BuildVPNSnapshotService(get_desired_accesses=lambda: accesses)

        snapshot = service(snapshot_revision=7)

        expected_payload = json.loads(
            (CONTRACT_FIXTURES / "canonical-two-accesses.json").read_text()
        )
        expected_canonical = (
            CONTRACT_FIXTURES / "canonical-two-accesses.canonical.json"
        ).read_bytes()
        self.assertEqual(snapshot.as_payload(), expected_payload)
        self.assertEqual(snapshot.canonical_bytes, expected_canonical)
        self.assertEqual(snapshot.snapshot_hash, expected_payload["snapshot_hash"])

    def test_empty_snapshot_matches_shared_fixture(self) -> None:
        snapshot = BuildVPNSnapshotService(
            get_desired_accesses=lambda: ()
        )(snapshot_revision=1)

        expected = json.loads(
            (CONTRACT_FIXTURES / "canonical-empty.json").read_text()
        )
        self.assertEqual(snapshot.as_payload(), expected)

    def test_payload_exposes_only_contract_fields_not_customer_or_secrets(self) -> None:
        access = _access(
            2,
            "01890f47-a2d4-7c11-b3e6-89f40d8639f1",
            1,
            customer_id=99,
        )
        snapshot = BuildVPNSnapshotService(
            get_desired_accesses=lambda: (access,)
        )(snapshot_revision=1)

        rendered = json.dumps(snapshot.as_payload())
        self.assertNotIn("customer", rendered)
        self.assertNotIn("published", rendered)
        self.assertNotIn("token", rendered)
        self.assertNotIn("secret", rendered)
        self.assertEqual(
            set(snapshot.as_payload()),
            {"schema_version", "snapshot_revision", "snapshot_hash", "accesses"},
        )

    def test_selector_uses_desired_set_and_represents_expire_refund_as_absence(self) -> None:
        now = timezone.now()
        active = VPNAccessFactory(
            desired_uuid=UUID("01890f47-a2d4-7c11-b3e6-89f40d8639f1"),
            desired_revision=3,
            published_uuid=UUID("2f1c5a63-7bd6-4ac1-86dc-16b7adf580df"),
            published_revision=2,
            expired_at=now + timedelta(days=1),
            state=VPNAccessState.PREPARING,
        )
        ready_uuid = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        ready = VPNAccessFactory(
            expired_at=now + timedelta(days=2),
            state=VPNAccessState.READY,
            desired_uuid=ready_uuid,
            published_uuid=ready_uuid,
            published_revision=1,
        )
        VPNAccessFactory(
            expired_at=now,
            state=VPNAccessState.EXPIRED,
        )
        actor = SystemUserFactory()
        VPNAccessFactory(
            expired_at=now + timedelta(days=1),
            state=VPNAccessState.DISABLED_REFUND,
            disabled_at=now,
            disabled_reason="operator refund",
            disabled_by=actor,
        )
        inactive = VPNAccessFactory(expired_at=now + timedelta(days=1))
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])

        selected = tuple(get_desired_vpn_snapshot_accesses(at=now))

        self.assertEqual([item.access_id for item in selected], sorted([active.pk, ready.pk]))
        selected_active = next(item for item in selected if item.access_id == active.pk)
        self.assertEqual(selected_active.uuid, active.desired_uuid)
        self.assertEqual(selected_active.access_revision, 3)
        self.assertNotEqual(selected_active.uuid, active.published_uuid)

    def test_add_renew_and_reissue_are_exact_desired_sets(self) -> None:
        existing = _access(
            2,
            "01890f47-a2d4-7c11-b3e6-89f40d8639f1",
            1,
            customer_id=20,
        )
        added = _access(
            10,
            "2f1c5a63-7bd6-4ac1-86dc-16b7adf580df",
            1,
            customer_id=30,
        )
        renewed = _access(
            2,
            "01890f47-a2d4-7c11-b3e6-89f40d8639f1",
            1,
            customer_id=20,
        )
        reissued = _access(
            2,
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            2,
            customer_id=20,
        )

        add = BuildVPNSnapshotService(
            get_desired_accesses=lambda: (existing, added)
        )(snapshot_revision=2)
        renew = BuildVPNSnapshotService(
            get_desired_accesses=lambda: (renewed,)
        )(snapshot_revision=2)
        reissue = BuildVPNSnapshotService(
            get_desired_accesses=lambda: (reissued,)
        )(snapshot_revision=3)

        self.assertEqual([item.access_id for item in add.accesses], [2, 10])
        self.assertEqual(renew.accesses, (renewed,))
        self.assertEqual(reissue.accesses, (reissued,))

    def test_capacity_forecast_is_exact_at_entry_and_byte_boundaries(self) -> None:
        existing = _access(
            2,
            "01890f47-a2d4-7c11-b3e6-89f40d8639f1",
            1,
            customer_id=20,
        )
        prospective = _access(
            10,
            "2f1c5a63-7bd6-4ac1-86dc-16b7adf580df",
            1,
            customer_id=30,
        )
        probe = ForecastVPNSnapshotCapacityService(
            get_desired_accesses=lambda: (existing,),
            max_entries=2,
            max_canonical_bytes=1_048_576,
        )(snapshot_revision=2, prospective_access=prospective)

        exact = ForecastVPNSnapshotCapacityService(
            get_desired_accesses=lambda: (existing,),
            max_entries=2,
            max_canonical_bytes=probe.canonical_bytes,
        )(snapshot_revision=2, prospective_access=prospective)
        over_entries = ForecastVPNSnapshotCapacityService(
            get_desired_accesses=lambda: (existing,),
            max_entries=1,
            max_canonical_bytes=probe.canonical_bytes,
        )(snapshot_revision=2, prospective_access=prospective)
        over_bytes = ForecastVPNSnapshotCapacityService(
            get_desired_accesses=lambda: (existing,),
            max_entries=2,
            max_canonical_bytes=probe.canonical_bytes - 1,
        )(snapshot_revision=2, prospective_access=prospective)

        self.assertTrue(exact.fits)
        self.assertEqual(exact.entries, 2)
        self.assertFalse(over_entries.fits)
        self.assertFalse(over_bytes.fits)

    def test_customer_renewal_or_reissue_replaces_instead_of_incrementing(self) -> None:
        existing = _access(
            2,
            "01890f47-a2d4-7c11-b3e6-89f40d8639f1",
            1,
            customer_id=20,
        )
        reissue_for_same_customer = _access(
            99,
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            2,
            customer_id=20,
        )
        forecast = ForecastVPNSnapshotCapacityService(
            get_desired_accesses=lambda: (existing,),
            max_entries=1,
            max_canonical_bytes=1_048_576,
        )(
            snapshot_revision=2,
            prospective_access=reissue_for_same_customer,
        )

        self.assertTrue(forecast.fits)
        self.assertEqual(forecast.entries, 1)

    def test_factories_wire_selector_without_http_transport(self) -> None:
        builder = get_build_vpn_snapshot_service()
        forecast = get_forecast_vpn_snapshot_capacity_service()

        self.assertIsInstance(builder, BuildVPNSnapshotService)
        self.assertIsInstance(forecast, ForecastVPNSnapshotCapacityService)
        self.assertFalse(hasattr(builder, "transport"))
        self.assertFalse(hasattr(forecast, "transport"))
