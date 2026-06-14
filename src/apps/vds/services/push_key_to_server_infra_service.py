from __future__ import annotations

from dataclasses import dataclass
from typing import final

import requests
from django.conf import settings

from apps.vds.selectors import get_vds_instance_by_id


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class PushKeyToServerInfraService:
    """Идемпотентно доставляет один секрет на один здоровый VDS.

    Сначала POST. Если пользователь уже есть (409) — секрет ротируется через
    PATCH: при перевыпуске токен меняется, и новый секрет обязан заместить
    старый на сервере (иначе старая ссылка продолжит работать). PATCH тем же
    секретом — безопасный no-op, поэтому повторная доставка остаётся идемпотентной.
    Прочие ошибки пробрасываются для ретрая на уровне таска.
    """

    def __call__(self, *, server_id: int, username: str, secret: str) -> None:
        server = get_vds_instance_by_id(pk=server_id)
        response = requests.post(
            url=f"{server.internal_url}/api/users",
            json={"username": username, "secret": secret},
            timeout=settings.VDS_REQUEST_TIMEOUT,
        )
        if response.status_code == 409:
            response = requests.patch(
                url=f"{server.internal_url}/api/users",
                json={"username": username, "secret": secret},
                timeout=settings.VDS_REQUEST_TIMEOUT,
            )
        response.raise_for_status()


def get_push_key_to_server_infra_service() -> PushKeyToServerInfraService:
    return PushKeyToServerInfraService()
