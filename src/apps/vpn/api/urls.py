from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("v1/vpn/", include("apps.vpn.api.v1.urls")),
]
