from __future__ import annotations

from dataclasses import dataclass
from typing import final

import requests

from apps.vds.selectors import get_vds_instance_by_id

_HEALTH_CHECK_TIMEOUT = 5


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VDSHealthCheckInfraService:
    def __call__(self, *, instance_id: int) -> bool:
        server = get_vds_instance_by_id(pk=instance_id)
        try:
            requests.get(url=server.internal_url, timeout=_HEALTH_CHECK_TIMEOUT)
            return True
        except Exception:
            return False


def get_vds_health_check_infra_service() -> VDSHealthCheckInfraService:
    return VDSHealthCheckInfraService()
