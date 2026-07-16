from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, final

from django.conf import settings

from apps.vpn.exceptions import VPNCapacityUnavailable, VPNSalesDisabled
from apps.vpn.selectors import (
    get_active_unexpired_vpn_access_by_user_id,
    has_compatible_ready_vpn_node_with_capacity,
)

if TYPE_CHECKING:
    from apps.users.models import SystemUser
    from apps.vpn.models import VPNAccess

SNAPSHOT_V1_MAX_ENTRIES = 5_000


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CheckVPNSaleAvailabilityService:
    """Fail closed unless a new VLESS access can be sold right now."""

    sales_enabled: bool
    get_active_unexpired_access: Callable[..., VPNAccess | None]
    has_compatible_capacity: Callable[..., bool]

    def __call__(self, *, customer: SystemUser) -> None:
        if not self.sales_enabled:
            raise VPNSalesDisabled(customer.username)
        existing_access = self.get_active_unexpired_access(user_id=customer.pk)
        prospective_increment = 0 if existing_access is not None else 1
        if not self.has_compatible_capacity(
            prospective_increment=prospective_increment
        ):
            raise VPNCapacityUnavailable(customer.username)


def get_check_vpn_sale_availability_service() -> CheckVPNSaleAvailabilityService:
    return CheckVPNSaleAvailabilityService(
        sales_enabled=settings.VPN_SALES_ENABLED,
        get_active_unexpired_access=get_active_unexpired_vpn_access_by_user_id,
        has_compatible_capacity=partial(
            has_compatible_ready_vpn_node_with_capacity,
            contract_version=settings.VPN_AGENT_CONTRACT_VERSION,
            max_snapshot_entries=SNAPSHOT_V1_MAX_ENTRIES,
        ),
    )
