from __future__ import annotations

import os
from dataclasses import dataclass
from typing import final

import requests
from django.conf import settings

from apps.core.decorators import log_infra_error
from apps.vds.exceptions import VDSConnectionLimit, VDSNotAvailable
from apps.vds.models import VDSInstance
from apps.vds.selectors import get_keys_by_username
from apps.vds.services.dtos import VDSKeyResponseOut
from apps.vds.tasks import add_key_to_another_vds_instances_task


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class AddNewKeyInfraService:
    @log_infra_error
    def __call__(self, *, server: VDSInstance, username: str) -> VDSKeyResponseOut | None:
        self._check_vds_limit(server=server, username=username)
        try:
            secret = str(os.urandom(16).hex())
            response = requests.post(
                url=f"{server.internal_url}/api/users",
                json={"username": username, "secret": secret},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            get_keys_by_username(username=username).delete()
            add_key_to_another_vds_instances_task.delay(
                exclude=server.pk,
                username=username,
                secret=secret,
            )
            return VDSKeyResponseOut(**response.json())
        except Exception as exc:
            raise VDSNotAvailable(
                method="add-user",
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

    @classmethod
    def _check_vds_limit(cls, *, server: VDSInstance, username: str) -> None:
        if not server.is_available():
            raise VDSConnectionLimit(
                method="add-user",
                telegram_id=username,
                server=dict(
                    id=server.pk,
                    name=server.name,
                    ip=server.ip_address,
                    port=server.port,
                    url=server.external_url,
                ),
            )


def get_add_new_key_service_factory() -> AddNewKeyInfraService:
    return AddNewKeyInfraService()
