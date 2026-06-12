from __future__ import annotations

from dataclasses import dataclass
from typing import final

import requests
from django.conf import settings

from apps.vds.selectors import get_vds_instance_by_id


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReplicateKeyAddToServerInfraService:
    def __call__(self, *, server_id: int, username: str, secret: str) -> None:
        server = get_vds_instance_by_id(pk=server_id)
        response = requests.post(
            url=f"{server.internal_url}/api/users",
            json={"username": username, "secret": secret},
            timeout=settings.VDS_REQUEST_TIMEOUT,
        )
        if response.status_code == 409:
            return
        response.raise_for_status()


def get_replicate_key_add_to_server_infra_service() -> ReplicateKeyAddToServerInfraService:
    return ReplicateKeyAddToServerInfraService()
