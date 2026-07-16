from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING, final

from django.db import transaction

from apps.payments.services.dtos import (
    VPNPaymentFulfillmentIn,
    VPNPaymentFulfillmentOut,
)
from apps.vpn.enums import VPNAccessState
from apps.vpn.models import VPNAccess, VPNPurchase
from apps.vpn.selectors import (
    get_any_vpn_access_by_user_id,
    get_vpn_purchase_by_payment_id,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def register_after_commit(callback: Callable[[], None]) -> None:
    """Run delivery acceleration after the owning outer transaction commits."""
    transaction.on_commit(callback, robust=True)


def _save_access(*, access: VPNAccess, update_fields: Sequence[str]) -> None:
    access.save(update_fields=update_fields)


def _noop_schedule_delivery(*, access_id: int) -> None:
    """Leave delivery to periodic reconcile until B-009 supplies acceleration."""


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FulfillPurchaseService:
    """Create or renew the unique VPN access for one applied payment."""

    get_access: Callable[..., VPNAccess | None]
    get_purchase: Callable[..., VPNPurchase | None]
    create_access: Callable[..., VPNAccess]
    save_access: Callable[..., None]
    create_purchase: Callable[..., VPNPurchase]
    register_after_commit: Callable[[Callable[[], None]], None]
    schedule_delivery: Callable[..., None]

    def __call__(
        self,
        *,
        purchase: VPNPaymentFulfillmentIn,
    ) -> VPNPaymentFulfillmentOut:
        with transaction.atomic():
            existing_purchase = self.get_purchase(payment_id=purchase.payment_id)
            if existing_purchase is not None:
                return VPNPaymentFulfillmentOut(
                    access_id=existing_purchase.access_id,
                    purchase_id=existing_purchase.pk,
                )

            access = self.get_access(user_id=purchase.user_id)
            if access is None:
                expired_at = purchase.accepted_at + timedelta(days=30)
                access = self.create_access(
                    user_id=purchase.user_id,
                    expired_at=expired_at,
                    state=VPNAccessState.PREPARING,
                )
            else:
                was_expired = access.expired_at <= purchase.accepted_at
                access.expired_at = max(access.expired_at, purchase.accepted_at) + timedelta(
                    days=30
                )
                update_fields = ["expired_at", "updated_at"]
                if was_expired and access.state != VPNAccessState.PREPARING:
                    access.state = VPNAccessState.PREPARING
                    access.state_revision += 1
                    update_fields.extend(("state", "state_revision"))
                self.save_access(access=access, update_fields=update_fields)

            purchase_audit = self.create_purchase(
                payment_id=purchase.payment_id,
                access=access,
                period_days=30,
                expired_at_after=access.expired_at,
            )
            try:
                self.register_after_commit(
                    partial(self.schedule_delivery, access_id=access.pk)
                )
            except Exception:
                # Periodic reconcile remains the durable delivery mechanism.
                pass
            return VPNPaymentFulfillmentOut(
                access_id=access.pk,
                purchase_id=purchase_audit.pk,
            )


def get_fulfill_purchase_service(
    *,
    schedule_delivery: Callable[..., None] = _noop_schedule_delivery,
    register_after_commit_callback: Callable[[Callable[[], None]], None] = register_after_commit,
) -> FulfillPurchaseService:
    return FulfillPurchaseService(
        get_access=get_any_vpn_access_by_user_id,
        get_purchase=get_vpn_purchase_by_payment_id,
        create_access=VPNAccess.objects.create,
        save_access=_save_access,
        create_purchase=VPNPurchase.objects.create,
        register_after_commit=register_after_commit_callback,
        schedule_delivery=schedule_delivery,
    )
