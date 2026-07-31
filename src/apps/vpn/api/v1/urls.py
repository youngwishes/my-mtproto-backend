from __future__ import annotations

from django.urls import path

from apps.vpn.api.v1.views import FulfillVPNPaymentView

urlpatterns = [
    path("payments/buy/", FulfillVPNPaymentView.as_view(), name="vpn-payment-buy"),
]
