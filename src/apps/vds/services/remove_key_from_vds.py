from collections.abc import Iterable
from dataclasses import dataclass
import requests
from django.db.models import QuerySet

from apps.vds.models import VDSInstance, MTPRotoKey
from apps.vds.services.exceptions import VDSNotAvailable


@dataclass(kw_only=True, slots=True, frozen=True)
class RemoveUserKeyService:
    def __call__(self, *, keys: QuerySet[MTPRotoKey]) -> None:
        servers: Iterable[VDSInstance] = VDSInstance.objects.all()
        usernames = []
        for server in servers:
            try:
                filtered_keys = keys.filter(vds=server)
                usernames = list(
                    filtered_keys
                    .values_list("user__username", flat=True)
                    .distinct()
                )
                if not usernames:
                    return
                response = requests.post(
                    f"{server.url}/api/v1/remove-user",
                    json={"usernames": usernames},
                    timeout=8,
                )
                response.raise_for_status()
                filtered_keys.update(is_active=False, was_deleted=True)
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
                        url=server.url,
                    ),
                )


def get_remove_user_key_service() -> RemoveUserKeyService:
    return RemoveUserKeyService()
