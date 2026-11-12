from __future__ import annotations

from django.conf import settings
from rest_framework.test import APITestCase


class TestVPNBotSettings(APITestCase):
    def test_defaults_off_and_requires_bot_auth(self):
        url = "/api/v1/vpn/bot-settings/"
        self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.get(
            url, headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"enabled": False})

    def test_toggle_is_visible_immediately_and_preserves_subscription(self):
        from apps.vpn.models import VPNBotSettings
        from apps.vpn.tests.factories import VPNSubscriptionFactory

        subscription = VPNSubscriptionFactory()
        original = (
            subscription.token,
            subscription.vless_uuid,
            subscription.hysteria_secret,
            subscription.expired_at,
            subscription.is_active,
        )
        for enabled in (True, False, True):
            VPNBotSettings.objects.filter(pk=1).update(is_active=enabled)
            response = self.client.get(
                "/api/v1/vpn/bot-settings/",
                headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
            )
            self.assertEqual(response.json(), {"enabled": enabled})
            subscription.refresh_from_db()
            self.assertEqual(
                (
                    subscription.token,
                    subscription.vless_uuid,
                    subscription.hysteria_secret,
                    subscription.expired_at,
                    subscription.is_active,
                ),
                original,
            )

    def test_admin_can_toggle_existing_settings_but_not_add_or_delete(self):
        from django.urls import reverse
        from apps.users.tests.factories import SystemUserFactory
        from apps.vpn.models import VPNBotSettings

        admin = SystemUserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(admin)
        url = reverse("admin:vpn_vpnbotsettings_change", args=[1])
        response = self.client.get(url)
        self.assertContains(response, "VPN доступен в боте")
        for data, expected in (
            ({"is_active": "on", "_save": "Save"}, True),
            ({"_save": "Save"}, False),
        ):
            self.assertEqual(self.client.post(url, data).status_code, 302)
            self.assertEqual(VPNBotSettings.objects.get(pk=1).is_active, expected)
        self.assertEqual(
            self.client.get(reverse("admin:vpn_vpnbotsettings_add")).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                reverse("admin:vpn_vpnbotsettings_delete", args=[1]), {"post": "yes"}
            ).status_code,
            403,
        )
