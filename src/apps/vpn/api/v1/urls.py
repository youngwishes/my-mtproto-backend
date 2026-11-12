from __future__ import annotations

from django.urls import path

from apps.vpn.api.v1.views import (
    AgentBootstrapProfilesView,
    FulfillVPNPaymentView,
    ReissueVPNSubscriptionView,
    VPNMenuView,
    VPNSubscriptionView,
)
from apps.vpn.api.v1.views.bot_settings_views import VPNBotSettingsView

urlpatterns = [
    path("bot-settings/", VPNBotSettingsView.as_view(), name="vpn-bot-settings"),
    path(
        "agent/profiles/",
        AgentBootstrapProfilesView.as_view(),
        name="vpn-agent-profiles",
    ),
    path("menu/", VPNMenuView.as_view(), name="vpn-menu"),
    path("payments/buy/", FulfillVPNPaymentView.as_view(), name="vpn-payment-buy"),
    path("reissue/", ReissueVPNSubscriptionView.as_view(), name="vpn-reissue"),
    path(
        "subscriptions/<str:token>/",
        VPNSubscriptionView.as_view(),
        name="vpn-subscription",
    ),
]
