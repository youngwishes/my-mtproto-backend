from __future__ import annotations

from dataclasses import dataclass
from typing import final

from apps.vds.selectors import get_all_active_vds_instances, get_expired_keys_for_vds_instance, get_vds_instance_by_id
from apps.vds.services.remove_key_infra_service import get_remove_user_key_infra_service


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class RemoveExpiredKeysFromVdsInfraService:
    def __call__(self, *, instance_id: int) -> None:
        instance = get_vds_instance_by_id(pk=instance_id)
        keys = get_expired_keys_for_vds_instance(instance=instance)

        if not keys.exists():
            return

        service = get_remove_user_key_infra_service()
        for server in get_all_active_vds_instances():
            service(server=server, keys=keys)

        keys.update(is_active=False, was_deleted=True)


def get_remove_expired_keys_from_vds_infra_service() -> RemoveExpiredKeysFromVdsInfraService:
    return RemoveExpiredKeysFromVdsInfraService()
