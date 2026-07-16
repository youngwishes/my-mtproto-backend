from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True, slots=True, frozen=True)
class VPNAgentNodeDTO:
    node_id: int
    base_url: str
    secret_key: str
    contract_version: str


@dataclass(kw_only=True, slots=True, frozen=True)
class VPNAgentHealthDTO:
    contract_version: str
    schema_version: str
    agent_sha: str
    xray_version: str
    xray_image_digest: str
    readiness: str
    applied_snapshot_revision: int | None
    applied_snapshot_hash: str | None


@dataclass(kw_only=True, slots=True, frozen=True)
class VPNAgentSnapshotMetadataDTO:
    contract_version: str
    schema_version: str
    snapshot_revision: int | None
    snapshot_hash: str | None


@dataclass(kw_only=True, slots=True, frozen=True)
class VPNAgentApplyResultDTO:
    schema_version: str
    snapshot_revision: int
    snapshot_hash: str
    result: str
