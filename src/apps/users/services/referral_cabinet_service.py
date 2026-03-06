from dataclasses import dataclass, asdict

from apps.users.models import SystemUser


@dataclass(kw_only=True, slots=True, frozen=True)
class Response:
    total_referrals_count: int | None
    active_referrals_count: int | None
    referral_link: str | None
    link_activated_count: int | None

    def asdict(self) -> dict:
        return asdict(self)


@dataclass(kw_only=True, slots=True, frozen=True)
class ReferralCabinetService:
    def __call__(self, *, username: str) -> Response:
        try:
            user = SystemUser.objects.get(username=username)
        except SystemUser.DoesNotExist:
            return Response(
                total_referrals_count=None,
                active_referrals_count=None,
                referral_link=None,
                link_activated_count=None,
            )
        return Response(
            total_referrals_count=SystemUser.objects.filter(
                invited_from_username=username
            ).count(),
            active_referrals_count=SystemUser.objects.filter(
                invited_from_username=username, referral_activated=True
            ).count(),
            referral_link=user.referral_link,
            link_activated_count=user.referral_link_activated_count,
        )


def get_referral_cabinet_service() -> ReferralCabinetService:
    return ReferralCabinetService()
