from __future__ import annotations

from django.urls import path

from apps.vpn.api.v1.views import VPNSubscriptionView

urlpatterns = [
    path("subscriptions/<str:token>/", VPNSubscriptionView.as_view(), name="vpn-subscription"),
]
