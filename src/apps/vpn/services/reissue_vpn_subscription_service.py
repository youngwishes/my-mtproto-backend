from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, Protocol, final
from uuid import UUID, uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.decorators import log_service_error
from apps.users.selectors import get_user_by_username
from apps.vpn.exceptions import VPNReissueCooldown, VPNReissueUnavailable
from apps.vpn.models import _generate_hysteria_secret, _generate_subscription_token
from apps.vpn.selectors import get_vpn_subscription_by_user_id
from apps.vpn.services.dtos.subscription_dtos import VPNReissueOut
from apps.vpn.services.schedule_profiles_service import get_schedule_profiles_service


class ScheduleProfiles(Protocol):
    def __call__(self, *, subscription_id: int) -> None: ...


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReissueVPNSubscriptionService:
    """Ротирует VPN credentials и планирует их асинхронную доставку после commit."""

    generate_token: Callable[[], str]
    generate_vless_uuid: Callable[[], UUID]
    generate_hysteria_secret: Callable[[], str]
    schedule_profiles: ScheduleProfiles
    subscription_base_url: str

    @log_service_error
    def __call__(self, *, username: str) -> VPNReissueOut:
        user = get_user_by_username(username=username)
        if user is None:
            raise VPNReissueUnavailable(telegram_id=username)
        subscription = get_vpn_subscription_by_user_id(user_id=user.pk)
        if subscription is None:
            raise VPNReissueUnavailable(telegram_id=username)
        now = timezone.now()
        if not subscription.is_active or subscription.expired_at <= now:
            raise VPNReissueUnavailable(telegram_id=username)
        if (
            subscription.last_reissued_at is not None
            and subscription.last_reissued_at + timedelta(minutes=5) > now
        ):
            raise VPNReissueCooldown(telegram_id=username)

        with transaction.atomic():
            subscription.token = self.generate_token()
            subscription.vless_uuid = self.generate_vless_uuid()
            subscription.hysteria_secret = self.generate_hysteria_secret()
            subscription.last_reissued_at = now
            subscription.save(
                update_fields=[
                    "token",
                    "vless_uuid",
                    "hysteria_secret",
                    "last_reissued_at",
                    "updated_at",
                ],
            )
            transaction.on_commit(
                lambda: self.schedule_profiles(subscription_id=subscription.pk),
            )

        return VPNReissueOut(
            expired_at=subscription.expired_at,
            subscription_url=(
                f"{self.subscription_base_url.rstrip('/')}/api/v1/vpn/subscriptions/"
                f"{subscription.token}/"
            ),
        )


def get_reissue_vpn_subscription_service() -> ReissueVPNSubscriptionService:
    return ReissueVPNSubscriptionService(
        generate_token=_generate_subscription_token,
        generate_vless_uuid=uuid4,
        generate_hysteria_secret=_generate_hysteria_secret,
        schedule_profiles=get_schedule_profiles_service(),
        subscription_base_url=settings.VPN_SUBSCRIPTION_BASE_URL,
    )
