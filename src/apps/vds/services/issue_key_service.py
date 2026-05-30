from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apps.vds.models import MTPRotoKey, VDSInstance
from apps.vds.services.add_new_key_infra_service import get_add_new_key_service_factory

if TYPE_CHECKING:
    from datetime import datetime

    from apps.tribute.models import TributeDigitalPayment
    from apps.users.models import SystemUser


@dataclass(kw_only=True, slots=True, frozen=True)
class IssueKeyService:
    """Выдаёт новый MTPRoto-ключ на наименее загруженном VDS."""

    def __call__(
        self,
        *,
        user: SystemUser,
        expired_date: datetime,
        payment: TributeDigitalPayment | None = None,
    ) -> MTPRotoKey:
        server = VDSInstance.objects.get_least_populated()
        response = get_add_new_key_service_factory()(
            server=server,
            username=str(user.username),
        )
        return MTPRotoKey.objects.create(
            vds=server,
            user=user,
            payment=payment,
            token=response.key,
            tls_domain=response.tls_domain,
            node_number=response.node_number,
            expired_date=expired_date,
        )


def get_issue_key_service() -> IssueKeyService:
    return IssueKeyService()
