from __future__ import annotations

from django.urls import path

from apps.vpn.api.v1.views import FulfillVPNPaymentView, VPNMenuView, VPNSubscriptionView

urlpatterns = [
    path("menu/", VPNMenuView.as_view(), name="vpn-menu"),
    path("payments/buy/", FulfillVPNPaymentView.as_view(), name="vpn-payment-buy"),
    path(
        "subscriptions/<str:token>/",
        VPNSubscriptionView.as_view(),
        name="vpn-subscription",
    ),
]
