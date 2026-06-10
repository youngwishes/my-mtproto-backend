from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

import requests
from django.conf import settings

from apps.core.decorators import log_infra_error
from apps.vds.exceptions import VDSNotAvailable
from apps.vds.services.dtos import VDSKeyResponseOut
from apps.vds.tasks import update_key_on_another_vds_instances_task

if TYPE_CHECKING:
    from apps.vds.models import VDSInstance


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class UpdateKeyInfraService:
    @log_infra_error
    def __call__(self, *, server: VDSInstance, username: str) -> VDSKeyResponseOut | None:
        try:
            secret = str(os.urandom(16).hex())
            response = requests.patch(
                url=f"{server.internal_url}/api/users",
                json={"username": username, "secret": secret},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            update_key_on_another_vds_instances_task.delay(
                exclude=server.pk, username=username, secret=secret
            )
            return VDSKeyResponseOut(**response.json())
        except Exception as exc:
            raise VDSNotAvailable(
                method="update-user",
                base_error=str(exc),
                telegram_id=username,
                server=dict(
                    id=server.pk,
                    name=server.name,
                    ip=server.ip_address,
                    port=server.port,
                    url=server.external_url,
                ),
            )


def get_update_key_infra_service() -> UpdateKeyInfraService:
    return UpdateKeyInfraService()
