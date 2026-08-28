from __future__ import annotations

from .first_free_link_serializer import (
    AcceptLegalConsentSerializer,
    FirstFreeLinkSerializer,
    CheckFirstFreeLinkSerializer,
    LegalConsentStatusSerializer,
)
from .referral_cabinet_serializer import ReferralCabinetSerializer
from .update_key_serializer import (
    UpdateKeySerializer,
)
from .my_servers_serializer import (
    MyServersSerializer,
)

__all__ = [
    "AcceptLegalConsentSerializer",
    "CheckFirstFreeLinkSerializer",
    "FirstFreeLinkSerializer",
    "LegalConsentStatusSerializer",
    "MyServersSerializer",
    "ReferralCabinetSerializer",
    "UpdateKeySerializer",
]
