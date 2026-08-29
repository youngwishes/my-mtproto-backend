from __future__ import annotations

from django.urls import path

from apps.fortune_wheel.api.views import (
    FortuneWheelSpinView,
    FortuneWheelStatusView,
)


urlpatterns = [
    path("status/", FortuneWheelStatusView.as_view(), name="fortune-wheel-status"),
    path("spin/", FortuneWheelSpinView.as_view(), name="fortune-wheel-spin"),
]
