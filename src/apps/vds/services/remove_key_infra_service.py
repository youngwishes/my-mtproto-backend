from copy import deepcopy
from dataclasses import dataclass
import requests
from django.conf import settings
from django.db.models import QuerySet

from apps.core.service import log_infra_error
from apps.vds.models import VDSInstance, MTPRotoKey
from apps.vds.services.exceptions import VDSNotAvailable


@dataclass(kw_only=True, slots=True, frozen=True)
class RemoveUserKeyInfraService:
    @log_infra_error
    def __call__(self, *, server: VDSInstance, keys: QuerySet[MTPRotoKey]) -> None:
        keys = deepcopy(keys)
        usernames = []
        try:
            usernames = list(
                keys.values_list("user__username", flat=True).distinct()
            )
            response = requests.post(
                f"{server.internal_url}/api/v2/users/remove",
                json={"usernames": usernames},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except Exception as exc:
            raise VDSNotAvailable(
                method="remove-user",
                telegram_id=usernames,
                base_error=str(exc),
                usernames=usernames,
                server=dict(
                    id=server.pk,
                    name=server.name,
                    ip=server.ip_address,
                    port=server.port,
                    url=server.external_url,
                ),
            )



def get_remove_user_key_infra_service() -> RemoveUserKeyInfraService:
    return RemoveUserKeyInfraService()
