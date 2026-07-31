from __future__ import annotations

from apps.vpn.api.v1.views.agent_bootstrap_views import AgentBootstrapProfilesView
from apps.vpn.api.v1.views.menu_views import VPNMenuView
from apps.vpn.api.v1.views.payment_views import FulfillVPNPaymentView
from apps.vpn.api.v1.views.subscription_views import VPNSubscriptionView

__all__ = [
    "AgentBootstrapProfilesView",
    "FulfillVPNPaymentView",
    "VPNMenuView",
    "VPNSubscriptionView",
]
