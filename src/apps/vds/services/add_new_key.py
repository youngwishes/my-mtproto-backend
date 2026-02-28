from dataclasses import dataclass

import requests
from django.conf import settings

from apps.core.service import log_infra_error
from apps.vds.models import VDSInstance
from apps.vds.services.exceptions import VDSConnectionLimit, VDSNotAvailable


@dataclass(kw_only=True, slots=True, frozen=True)
class Response:
    key: str
    tls_domain: str


@dataclass(kw_only=True, slots=True, frozen=True)
class AddNewKeyInfraService:
    @log_infra_error
    def __call__(self, *, server: VDSInstance, username: str) -> Response | None:
        self._check_vds_limit(server=server, username=username)
        try:
            response = requests.post(
                url=f"{server.internal_url}/api/v1/add-new-user",
                json={"username": username},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return Response(**response.json())
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
        if server.keys.count() > settings.VDS_MAX_USERS_COUNT:
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
