from dataclasses import dataclass
import requests
from apps.vds.models import VDSInstance


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
            )
            return Response(**response.json())
        except Exception:
            ...


def get_add_new_key_service_factory() -> AddNewKeyService:
    return AddNewKeyService()
