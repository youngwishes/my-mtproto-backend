from __future__ import annotations

from apps.users.services.legal_consent_accept_service import (
    AcceptLegalConsentService,
    get_accept_legal_consent_service,
)
from apps.users.services.legal_consent_status_service import (
    GetLegalConsentStatusService,
    get_legal_consent_status_service,
)
from apps.users.services.first_free_link_service import (
    FirstFreeLinkService,
    get_first_free_link_service,
)
from apps.users.services.check_first_free_link_service import (
    CheckFirstFreeLinkService,
    get_check_first_free_link_service,
)
from apps.users.services.referral_cabinet_service import (
    ReferralCabinetService,
    get_referral_cabinet_service,
)
from apps.users.services.get_free_link_via_referrals import (
    GetReferralVDSLinkService,
    get_referral_vds_link_service,
)
from apps.users.services.daily_free_trial_grant_service import (
    DailyFreeTrialGrantService,
    get_daily_free_trial_grant_service,
)

__all__ = [
    "AcceptLegalConsentService",
    "get_accept_legal_consent_service",
    "GetLegalConsentStatusService",
    "get_legal_consent_status_service",
    "FirstFreeLinkService",
    "get_first_free_link_service",
    "CheckFirstFreeLinkService",
    "get_check_first_free_link_service",
    "ReferralCabinetService",
    "get_referral_cabinet_service",
    "GetReferralVDSLinkService",
    "get_referral_vds_link_service",
    "DailyFreeTrialGrantService",
    "get_daily_free_trial_grant_service",
]
