from __future__ import annotations

from .first_free_link_view import (
    AcceptLegalConsentView,
    CheckFirstFreeLinkView,
    CreateFirstFreeLinkView,
    LegalConsentStatusView,
)
from .referral_cabinet_view import ReferralCabinetView, GetReferralLinkView
from .update_key_view import UpdateKeyView
from .my_servers_view import MyServersView

__all__ = [
    "AcceptLegalConsentView",
    "CheckFirstFreeLinkView",
    "CreateFirstFreeLinkView",
    "GetReferralLinkView",
    "LegalConsentStatusView",
    "MyServersView",
    "ReferralCabinetView",
    "UpdateKeyView",
]
