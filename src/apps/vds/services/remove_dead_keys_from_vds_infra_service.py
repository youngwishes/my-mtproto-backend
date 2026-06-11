from __future__ import annotations

from dataclasses import dataclass
from typing import final

from apps.vds.selectors import get_all_dead_expired_keys, get_vds_instance_by_id
from apps.vds.services.remove_key_infra_service import get_remove_user_key_infra_service


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class RemoveDeadKeysFromVdsInfraService:
    def __call__(self, *, instance_id: int) -> None:
        keys = get_all_dead_expired_keys()

        if not keys.exists():
            return

        server = get_vds_instance_by_id(pk=instance_id)
        get_remove_user_key_infra_service()(server=server, keys=keys)


def get_remove_dead_keys_from_vds_infra_service() -> RemoveDeadKeysFromVdsInfraService:
    return RemoveDeadKeysFromVdsInfraService()
