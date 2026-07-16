from __future__ import annotations

from django.apps import AppConfig


class VPNConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.vpn"
    verbose_name = "VPN"
