from __future__ import annotations

from django.urls import path

from apps.vpn.api.v1.views import (
    VPNPaymentIntentView,
    VPNPreCheckoutView,
    VPNReissueView,
    VPNStatusView,
    VPNSubscriptionView,
    VPNSuccessfulPaymentView,
)

urlpatterns = [
    path("payment-intents/", VPNPaymentIntentView.as_view(), name="vpn-payment-intent"),
    path("pre-checkout/", VPNPreCheckoutView.as_view(), name="vpn-pre-checkout"),
    path("payments/", VPNSuccessfulPaymentView.as_view(), name="vpn-payment"),
    path("status/", VPNStatusView.as_view(), name="vpn-status"),
    path("reissue/", VPNReissueView.as_view(), name="vpn-reissue"),
    path(
        "subscriptions/<str:token>/",
        VPNSubscriptionView.as_view(),
        name="vpn-subscription",
    ),
]
