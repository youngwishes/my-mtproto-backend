from __future__ import annotations

from dataclasses import dataclass
from typing import final

from django.utils import timezone

from apps.vds.selectors import get_all_active_vds_instances, get_keys_expired_up_to_date
from apps.vds.services.remove_key_infra_service import get_remove_user_key_infra_service


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class RemoveExpiredKeysFromVdsInfraService:
    def __call__(self) -> None:
        keys = get_keys_expired_up_to_date(date=timezone.now().date())

        if not keys.exists():
            return

        service = get_remove_user_key_infra_service()
        for server in get_all_active_vds_instances():
            service(server=server, keys=keys)

        keys.update(is_active=False, was_deleted=True)


def get_remove_expired_keys_from_vds_infra_service() -> RemoveExpiredKeysFromVdsInfraService:
    return RemoveExpiredKeysFromVdsInfraService()
