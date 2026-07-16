from __future__ import annotations

from typing import Protocol

from apps.vpn.dtos import (
    VPNAgentApplyResultDTO,
    VPNAgentHealthDTO,
    VPNAgentNodeDTO,
    VPNAgentSnapshotMetadataDTO,
    VPNExactSnapshotDTO,
)


class VPNAgentSecretResolver(Protocol):
    def __call__(self, *, secret_key: str) -> str: ...


class VPNAgentClient(Protocol):
    def get_health(self, *, node: VPNAgentNodeDTO) -> VPNAgentHealthDTO: ...

    def get_snapshot(
        self, *, node: VPNAgentNodeDTO
    ) -> VPNAgentSnapshotMetadataDTO: ...

    def put_snapshot(
        self, *, node: VPNAgentNodeDTO, snapshot: VPNExactSnapshotDTO
    ) -> VPNAgentApplyResultDTO: ...
