from __future__ import annotations

from django.conf import settings
from django.views.generic import TemplateView


class FortuneWheelPageView(TemplateView):
    template_name = "fortune_wheel/index.html"

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "spend_url": f"{settings.BOT_LINK}?start=apples_spend",
        }
