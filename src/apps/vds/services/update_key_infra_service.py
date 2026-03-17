from dataclasses import dataclass, asdict

import requests
from django.conf import settings

from apps.core.service import log_infra_error
from apps.vds.models import VDSInstance, MTPRotoKey
from apps.vds.services.exceptions import VDSNotAvailable


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
    def __call__(self, *, new_server: VDSInstance, old_key: MTPRotoKey, username: str) -> Response | None:
        try:
            response = requests.post(
                f"{old_key.vds.internal_url}/api/v1/remove-user",
                json={"usernames": [username]},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            response = requests.post(
                url=f"{new_server.internal_url}/api/v1/add-new-user",
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
                    id=new_server.pk,
                    name=new_server.name,
                    ip=new_server.ip_address,
                    port=new_server.port,
                    url=new_server.external_url,
                ),
            )


def get_update_key_infra_service() -> UpdateKeyInfraService:
    return UpdateKeyInfraService()
