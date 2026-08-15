from __future__ import annotations

import secrets
from uuid import uuid4

from django.db import models

from apps.core import BaseDjangoModel


def _generate_subscription_token() -> str:
    return secrets.token_urlsafe(32)


def _generate_hysteria_secret() -> str:
    return secrets.token_urlsafe(32)


class VPNSubscription(BaseDjangoModel):
    user = models.OneToOneField(
        "users.SystemUser",
        on_delete=models.CASCADE,
        related_name="vpn_subscription",
        verbose_name="пользователь",
    )
    token = models.CharField(
        "токен подписки",
        max_length=64,
        unique=True,
        default=_generate_subscription_token,
    )
    vless_uuid = models.UUIDField(
        "VLESS UUID",
        unique=True,
        default=uuid4,
    )
    hysteria_secret = models.CharField(
        "Hysteria credential",
        max_length=64,
        unique=True,
        default=_generate_hysteria_secret,
    )
    expired_at = models.DateTimeField("истекает")
    last_reissued_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"VPN subscription #{self.pk} — {self.user_id}"

    class Meta:
        verbose_name = "VPN-подписка"
        verbose_name_plural = "VPN-подписки"


class VPNInstance(BaseDjangoModel):
    number = models.PositiveSmallIntegerField("порядковый номер")
    name = models.CharField("название")
    location = models.CharField("локация", default="", blank=True)
    management_url = models.URLField("URL управления")
    public_host = models.CharField("публичный хост")
    vless_port = models.PositiveIntegerField("VLESS порт")
    reality_sni = models.CharField("REALITY SNI")
    reality_public_key = models.CharField("REALITY публичный ключ")
    reality_short_id = models.CharField("REALITY short ID")
    hysteria_port = models.PositiveIntegerField("Hysteria порт")
    hysteria_sni = models.CharField("Hysteria SNI")
    hysteria_obfs = models.CharField("Hysteria obfuscation")

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "VPN-нода"
        verbose_name_plural = "VPN-ноды"
        ordering = ["number", "pk"]
