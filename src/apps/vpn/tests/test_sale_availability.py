from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.vpn.enums import VPNAccessState, VPNNodeHealthState
from apps.vpn.exceptions import VPNCapacityUnavailable, VPNSalesDisabled
from apps.vpn.services.check_sale_availability import (
    CheckVPNSaleAvailabilityService,
    get_check_vpn_sale_availability_service,
)
from apps.vpn.tests.factories import VPNAccessFactory, VPNNodeFactory
from apps.users.tests.factories import SystemUserFactory


class CheckVPNSaleAvailabilityServiceTest(SimpleTestCase):
    def test_rejects_when_sales_flag_is_disabled_without_querying_capacity(
        self,
    ) -> None:
        has_capacity = Mock(return_value=True)
        service = CheckVPNSaleAvailabilityService(
            sales_enabled=False,
            get_active_unexpired_access=Mock(),
            has_compatible_capacity=has_capacity,
        )
        customer = SystemUserFactory.build()

        with self.assertRaises(VPNSalesDisabled):
            service(customer=customer)

        has_capacity.assert_not_called()

    def test_rejects_when_no_compatible_ready_node_has_capacity(self) -> None:
        service = CheckVPNSaleAvailabilityService(
            sales_enabled=True,
            get_active_unexpired_access=Mock(return_value=None),
            has_compatible_capacity=Mock(return_value=False),
        )

        with self.assertRaises(VPNCapacityUnavailable):
            service(customer=SystemUserFactory.build(username="123"))

    def test_accepts_when_flag_and_capacity_are_available(self) -> None:
        service = CheckVPNSaleAvailabilityService(
            sales_enabled=True,
            get_active_unexpired_access=Mock(return_value=None),
            has_compatible_capacity=Mock(return_value=True),
        )

        service(customer=SystemUserFactory.build(username="123"))

    def test_existing_active_unexpired_access_uses_zero_increment(self) -> None:
        access = Mock()
        has_capacity = Mock(return_value=True)
        customer = SystemUserFactory.build(pk=7, username="123")
        service = CheckVPNSaleAvailabilityService(
            sales_enabled=True,
            get_active_unexpired_access=Mock(return_value=access),
            has_compatible_capacity=has_capacity,
        )

        service(customer=customer)

        has_capacity.assert_called_once_with(prospective_increment=0)


class CheckVPNSaleAvailabilityFactoryTest(TestCase):
    @override_settings(VPN_SALES_ENABLED=True, VPN_AGENT_CONTRACT_VERSION="v1")
    def test_requires_exact_ready_synced_compatible_node(self) -> None:
        synced_hash = "a" * 64
        VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            agent_contract_version="v2",
            desired_snapshot_revision=1,
            applied_snapshot_revision=1,
            desired_snapshot_hash=synced_hash,
            applied_snapshot_hash=synced_hash,
        )
        service = get_check_vpn_sale_availability_service()
        customer = SystemUserFactory(username="123")

        with self.assertRaises(VPNCapacityUnavailable):
            service(customer=customer)

        VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            agent_contract_version="v1",
            desired_snapshot_revision=1,
            applied_snapshot_revision=1,
            desired_snapshot_hash=synced_hash,
            applied_snapshot_hash=synced_hash,
        )
        service(customer=customer)

    @override_settings(VPN_SALES_ENABLED=True, VPN_AGENT_CONTRACT_VERSION="v1")
    def test_at_exact_limit_renewal_is_allowed_but_first_and_expired_are_blocked(
        self,
    ) -> None:
        synced_hash = "b" * 64
        VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            agent_contract_version="v1",
            desired_snapshot_revision=1,
            applied_snapshot_revision=1,
            desired_snapshot_hash=synced_hash,
            applied_snapshot_hash=synced_hash,
        )
        accesses = []
        for index in range(5_000):
            accesses.append(
                VPNAccessFactory(
                    expired_at=timezone.now() + timedelta(days=1),
                    state=VPNAccessState.PREPARING,
                    user__username=f"capacity-user-{index}",
                )
            )
        service = get_check_vpn_sale_availability_service()

        service(customer=accesses[0].user)

        with self.assertRaises(VPNCapacityUnavailable):
            service(customer=SystemUserFactory(username="first-purchase"))

        expired = VPNAccessFactory(
            expired_at=timezone.now() - timedelta(seconds=1),
            state=VPNAccessState.EXPIRED,
            user__username="expired-reactivation",
        )
        with self.assertRaises(VPNCapacityUnavailable):
            service(customer=expired.user)

    @override_settings(VPN_SALES_ENABLED=True, VPN_AGENT_CONTRACT_VERSION="v1")
    def test_below_limit_first_purchase_is_allowed(self) -> None:
        synced_hash = "c" * 64
        VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            agent_contract_version="v1",
            desired_snapshot_revision=1,
            applied_snapshot_revision=1,
            desired_snapshot_hash=synced_hash,
            applied_snapshot_hash=synced_hash,
        )
        VPNAccessFactory(
            expired_at=timezone.now() + timedelta(days=1),
            state=VPNAccessState.PREPARING,
        )

        get_check_vpn_sale_availability_service()(
            customer=SystemUserFactory(username="new-user")
        )
