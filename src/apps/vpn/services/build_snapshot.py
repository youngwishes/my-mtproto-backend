from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import hashlib
from typing import final

from apps.vpn.dtos import (
    VPNDesiredAccessDTO,
    VPNExactSnapshotDTO,
    VPNSnapshotCapacityForecastDTO,
)
from apps.vpn.selectors import get_desired_vpn_snapshot_accesses

SNAPSHOT_V1_SCHEMA_VERSION = "1.0"
SNAPSHOT_V1_MAX_ENTRIES = 5_000
SNAPSHOT_V1_MAX_CANONICAL_BYTES = 1_048_576


def _ordered_accesses(
    accesses: Iterable[VPNDesiredAccessDTO],
) -> tuple[VPNDesiredAccessDTO, ...]:
    ordered = tuple(sorted(accesses, key=lambda access: access.access_id))
    if any(
        access.access_id < 1
        or access.access_revision < 1
        or (index > 0 and access.access_id == ordered[index - 1].access_id)
        for index, access in enumerate(ordered)
    ):
        raise ValueError("desired VPN accesses must have unique positive identifiers")
    return ordered


def _build_snapshot(
    *, snapshot_revision: int, accesses: Iterable[VPNDesiredAccessDTO]
) -> VPNExactSnapshotDTO:
    if snapshot_revision < 1:
        raise ValueError("snapshot revision must be positive")
    snapshot = VPNExactSnapshotDTO(
        schema_version=SNAPSHOT_V1_SCHEMA_VERSION,
        snapshot_revision=snapshot_revision,
        snapshot_hash="",
        accesses=_ordered_accesses(accesses),
    )
    return VPNExactSnapshotDTO(
        schema_version=snapshot.schema_version,
        snapshot_revision=snapshot.snapshot_revision,
        snapshot_hash=hashlib.sha256(snapshot.canonical_bytes).hexdigest(),
        accesses=snapshot.accesses,
    )


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class BuildVPNSnapshotService:
    """Build the deterministic complete desired set without performing HTTP."""

    get_desired_accesses: Callable[[], Iterable[VPNDesiredAccessDTO]]

    def __call__(self, *, snapshot_revision: int) -> VPNExactSnapshotDTO:
        return _build_snapshot(
            snapshot_revision=snapshot_revision,
            accesses=self.get_desired_accesses(),
        )


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ForecastVPNSnapshotCapacityService:
    """Forecast exact v1 entries and canonical bytes before mutation."""

    get_desired_accesses: Callable[[], Iterable[VPNDesiredAccessDTO]]
    max_entries: int
    max_canonical_bytes: int

    def __call__(
        self,
        *,
        snapshot_revision: int,
        prospective_access: VPNDesiredAccessDTO | None = None,
    ) -> VPNSnapshotCapacityForecastDTO:
        accesses = tuple(self.get_desired_accesses())
        if prospective_access is not None:
            accesses = tuple(
                access
                for access in accesses
                if not self._same_customer_or_access(
                    access=access, prospective_access=prospective_access
                )
            ) + (prospective_access,)
        snapshot = _build_snapshot(
            snapshot_revision=snapshot_revision,
            accesses=accesses,
        )
        entries = len(snapshot.accesses)
        canonical_bytes = len(snapshot.canonical_bytes)
        return VPNSnapshotCapacityForecastDTO(
            entries=entries,
            canonical_bytes=canonical_bytes,
            fits_entries=entries <= self.max_entries,
            fits_bytes=canonical_bytes <= self.max_canonical_bytes,
        )

    @staticmethod
    def _same_customer_or_access(
        *, access: VPNDesiredAccessDTO, prospective_access: VPNDesiredAccessDTO
    ) -> bool:
        if prospective_access.customer_id is not None:
            return access.customer_id == prospective_access.customer_id
        return access.access_id == prospective_access.access_id


def get_build_vpn_snapshot_service() -> BuildVPNSnapshotService:
    return BuildVPNSnapshotService(
        get_desired_accesses=get_desired_vpn_snapshot_accesses,
    )


def get_forecast_vpn_snapshot_capacity_service(
) -> ForecastVPNSnapshotCapacityService:
    return ForecastVPNSnapshotCapacityService(
        get_desired_accesses=get_desired_vpn_snapshot_accesses,
        max_entries=SNAPSHOT_V1_MAX_ENTRIES,
        max_canonical_bytes=SNAPSHOT_V1_MAX_CANONICAL_BYTES,
    )
