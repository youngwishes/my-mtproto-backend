from __future__ import annotations

from django.urls import path

from apps.users.api.v1.views import (
    AcceptLegalConsentView,
    CreateFirstFreeLinkView,
    CheckFirstFreeLinkView,
    LegalConsentStatusView,
    ReferralCabinetView,
    GetReferralLinkView,
    UpdateKeyView,
    MyServersView,
)

urlpatterns = [
    path(
        "consent/status/",
        LegalConsentStatusView.as_view(),
        name="legal-consent-status",
    ),
    path(
        "consent/accept/",
        AcceptLegalConsentView.as_view(),
        name="legal-consent-accept",
    ),
    path("first-free-link/", CreateFirstFreeLinkView.as_view(), name="first-free-link"),
    path(
        "check-first-free-link/",
        CheckFirstFreeLinkView.as_view(),
        name="check-first-free-link",
    ),
    path(
        "referral/cabinet/",
        ReferralCabinetView.as_view(),
        name="referral-cabinet",
    ),
    path("referral/link/", GetReferralLinkView.as_view(), name="get-referral-link"),
    path("update-link/", UpdateKeyView.as_view(), name="update-link"),
    path("my-servers/", MyServersView.as_view(), name="my-servers"),
]
