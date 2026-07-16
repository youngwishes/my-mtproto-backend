from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any
from uuid import UUID

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(kw_only=True, slots=True, frozen=True)
class VPNDesiredAccessDTO:
    access_id: int
    uuid: UUID
    access_revision: int
    customer_id: int | None = None

    def as_payload(self) -> dict[str, int | str]:
        return {
            "access_id": self.access_id,
            "uuid": str(self.uuid),
            "access_revision": self.access_revision,
        }


@dataclass(kw_only=True, slots=True, frozen=True)
class VPNExactSnapshotDTO:
    schema_version: str
    snapshot_revision: int
    snapshot_hash: str
    accesses: tuple[VPNDesiredAccessDTO, ...]

    @property
    def canonical_bytes(self) -> bytes:
        return json.dumps(
            {
                "schema_version": self.schema_version,
                "snapshot_revision": self.snapshot_revision,
                "accesses": [access.as_payload() for access in self.accesses],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    def as_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "snapshot_revision": self.snapshot_revision,
            "snapshot_hash": self.snapshot_hash,
            "accesses": [access.as_payload() for access in self.accesses],
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> VPNExactSnapshotDTO:
        try:
            if set(payload) != {
                "schema_version",
                "snapshot_revision",
                "snapshot_hash",
                "accesses",
            }:
                raise ValueError
            if payload["schema_version"] != "1.0":
                raise ValueError
            revision = payload["snapshot_revision"]
            snapshot_hash = payload["snapshot_hash"]
            raw_accesses = payload["accesses"]
            if (
                not isinstance(revision, int)
                or isinstance(revision, bool)
                or revision < 1
                or not isinstance(snapshot_hash, str)
                or _SHA256.fullmatch(snapshot_hash) is None
                or not isinstance(raw_accesses, list)
            ):
                raise ValueError
            accesses: list[VPNDesiredAccessDTO] = []
            for raw_access in raw_accesses:
                if not isinstance(raw_access, dict) or set(raw_access) != {
                    "access_id",
                    "uuid",
                    "access_revision",
                }:
                    raise ValueError
                access_id = raw_access["access_id"]
                access_revision = raw_access["access_revision"]
                raw_uuid = raw_access["uuid"]
                if (
                    not isinstance(access_id, int)
                    or isinstance(access_id, bool)
                    or access_id < 1
                    or not isinstance(access_revision, int)
                    or isinstance(access_revision, bool)
                    or access_revision < 1
                    or not isinstance(raw_uuid, str)
                ):
                    raise ValueError
                parsed_uuid = UUID(raw_uuid)
                if str(parsed_uuid) != raw_uuid:
                    raise ValueError
                accesses.append(
                    VPNDesiredAccessDTO(
                        access_id=access_id,
                        uuid=parsed_uuid,
                        access_revision=access_revision,
                    )
                )
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ValueError("invalid VPN snapshot contract payload") from None
        snapshot = cls(
            schema_version=payload["schema_version"],
            snapshot_revision=revision,
            snapshot_hash=snapshot_hash,
            accesses=tuple(accesses),
        )
        access_ids = [access.access_id for access in snapshot.accesses]
        if (
            access_ids != sorted(access_ids)
            or len(access_ids) != len(set(access_ids))
            or hashlib.sha256(snapshot.canonical_bytes).hexdigest()
            != snapshot.snapshot_hash
        ):
            raise ValueError("invalid VPN snapshot contract payload")
        return snapshot


@dataclass(kw_only=True, slots=True, frozen=True)
class VPNSnapshotCapacityForecastDTO:
    entries: int
    canonical_bytes: int
    fits_entries: bool
    fits_bytes: bool

    @property
    def fits(self) -> bool:
        return self.fits_entries and self.fits_bytes
