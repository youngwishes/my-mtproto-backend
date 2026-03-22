import os
from dataclasses import dataclass, asdict

import requests
from django.conf import settings

from apps.core.service import log_infra_error
from apps.vds.models import VDSInstance, MTPRotoKey
from apps.vds.services.exceptions import VDSNotAvailable
from apps.vds.tasks import (
    remove_key_from_another_vds_instances_task,
    add_key_to_another_vds_instances_task,
)


@dataclass(kw_only=True, slots=True, frozen=True)
class Response:
    key: str
    tls_domain: str
    node_number: str

    def asdict(self) -> dict:
        return asdict(self)


@dataclass(kw_only=True, slots=True, frozen=True)
class UpdateKeyInfraService:
    @log_infra_error
    def __call__(self, *, old_key: MTPRotoKey, username: str) -> Response | None:
        try:
            for server in VDSInstance.objects.all():
                remove_key_from_another_vds_instances_task(
                    server=server.pk, keys_id=[old_key.pk]
                )
            secret = str(os.urandom(16).hex())
            response = requests.post(
                url=f"{old_key.vds.internal_url}/api/v1/add-new-user",
                json={"username": username, "secret": secret},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            add_key_to_another_vds_instances_task.delay(
                exclude=old_key.vds.pk, username=username, secret=secret
            )
            return Response(**response.json())
        except Exception as exc:
            raise VDSNotAvailable(
                method="add-user",
                base_error=str(exc),
                telegram_id=username,
                server=dict(
                    id=old_key.vds.pk,
                    name=old_key.vds.name,
                    ip=old_key.vds.ip_address,
                    port=old_key.vds.port,
                    url=old_key.vds.external_url,
                ),
            )


def get_update_key_infra_service() -> UpdateKeyInfraService:
    return UpdateKeyInfraService()
