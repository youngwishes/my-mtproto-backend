from dataclasses import dataclass

import requests

from apps.core.service import BaseServiceError
from apps.vds.models import VDSInstance


class VDSNotAvailable(BaseServiceError):
    """VDS not available"""


@dataclass(kw_only=True, slots=True, frozen=True)
class Response:
    key: str
    tls_domain: str


@dataclass(kw_only=True, slots=True, frozen=True)
class AddNewKeyService:
    def __call__(self, *, server: VDSInstance, username: str) -> Response | None:
        try:
            response = requests.post(
                url=f"{server.url}/api/v1/add-new-user",
                json={"username": username},
                timeout=5,
            )
            return Response(**response.json())
        except Exception as exc:
            raise VDSNotAvailable(
                base_error=str(exc),
                telegram_id=username,
                server=dict(
                    id=server.pk,
                    name=server.name,
                    ip=server.ip_address,
                    port=server.port,
                    url=server.url,
                ),
            )


def get_add_new_key_service_factory() -> AddNewKeyService:
    return AddNewKeyService()
