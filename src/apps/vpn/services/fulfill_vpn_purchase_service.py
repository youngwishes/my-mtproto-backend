from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Protocol, final

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.decorators import log_service_error
from apps.payments.enums import ProductCodeEnum
from apps.payments.exceptions import BadPaymentData
from apps.payments.selectors.common import (
    create_vpn_payment,
    get_vpn_payment_by_identity,
    get_vpn_payment_by_identity_for_update,
)
from apps.users.selectors import get_user_by_username
from apps.vpn.selectors import (
    create_vpn_subscription,
    get_vpn_subscription_by_user_id,
    get_vpn_subscription_for_update,
)
from apps.vpn.services.dtos import FulfillVPNPaymentIn, VPNPurchaseOut
from apps.vpn.services.schedule_profiles_service import get_schedule_profiles_service

if TYPE_CHECKING:
    from apps.vpn.models import VPNSubscription


class ScheduleProfiles(Protocol):
    def __call__(self, *, subscription_id: int) -> None: ...


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FulfillVPNPurchaseService:
    """Атомарно фиксирует VPN-платёж и выдаёт или продлевает доступ."""

    schedule_profiles: ScheduleProfiles
    subscription_base_url: str

    @log_service_error
    def __call__(self, *, payment: FulfillVPNPaymentIn) -> VPNPurchaseOut:
        if payment.product_code != ProductCodeEnum.VPN_30D:
            raise BadPaymentData(telegram_id=payment.username)

        try:
            with transaction.atomic():
                user = get_user_by_username(username=payment.username)
                if user is None:
                    raise BadPaymentData(telegram_id=payment.username)

                existing_payment = get_vpn_payment_by_identity_for_update(
                    provider=payment.provider,
                    charge_id=payment.charge_id,
                )
                if existing_payment is not None:
                    subscription = get_vpn_subscription_for_update(
                        user_id=existing_payment.user_id,
                    )
                    if subscription is None:
                        raise BadPaymentData(telegram_id=payment.username)
                    return self._result(subscription=subscription)

                accepted_at = timezone.now()
                subscription = get_vpn_subscription_for_update(user_id=user.pk)
                if subscription is None:
                    subscription = create_vpn_subscription(
                        user=user,
                        expired_at=(
                            accepted_at
                            + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS)
                        ),
                    )
                elif subscription.is_active and subscription.expired_at > accepted_at:
                    subscription.expired_at += timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS)
                    subscription.save(update_fields=["expired_at", "updated_at"])
                else:
                    subscription.is_active = True
                    subscription.expired_at = accepted_at + timedelta(
                        days=settings.SUBSCRIPTION_PERIOD_DAYS,
                    )
                    subscription.save(
                        update_fields=["is_active", "expired_at", "updated_at"],
                    )

                create_vpn_payment(
                    user_id=user.pk,
                    provider=payment.provider,
                    charge_id=payment.charge_id,
                )
                transaction.on_commit(
                    lambda: self.schedule_profiles(subscription_id=subscription.pk),
                )
                return self._result(subscription=subscription)
        except IntegrityError:
            existing_payment = get_vpn_payment_by_identity(
                provider=payment.provider,
                charge_id=payment.charge_id,
            )
            if existing_payment is None:
                raise
            subscription = get_vpn_subscription_by_user_id(user_id=existing_payment.user_id)
            if subscription is None:
                raise BadPaymentData(telegram_id=payment.username)
            return self._result(subscription=subscription)

    def _result(self, *, subscription: VPNSubscription) -> VPNPurchaseOut:
        return VPNPurchaseOut(
            expired_at=subscription.expired_at,
            subscription_url=(
                f"{self.subscription_base_url.rstrip('/')}/api/v1/vpn/subscriptions/"
                f"{subscription.token}/"
            ),
        )


def get_fulfill_vpn_purchase_service() -> FulfillVPNPurchaseService:
    return FulfillVPNPurchaseService(
        schedule_profiles=get_schedule_profiles_service(),
        subscription_base_url=settings.VPN_SUBSCRIPTION_BASE_URL,
    )
