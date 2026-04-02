from django.urls import path
from apps.users.api.v1.views import (
    CreateFirstFreeLinkView,
    CheckFirstFreeLinkView,
    ReferralCabinetView,
    GetReferralLinkView,
    UpdateKeyView,
)
from apps.users.api.v1.views import UserAgreementView

urlpatterns = [
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
    path("check-agreement/", UserAgreementView.as_view(), name="user-agreement"),
]
