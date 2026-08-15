from __future__ import annotations

from base64 import b64decode
from datetime import timedelta
from unittest.mock import Mock, patch
from uuid import UUID

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.tests.factories import SystemUserFactory
from apps.vpn.exceptions import VPNReissueCooldown, VPNReissueUnavailable
from apps.vpn.selectors import get_active_vpn_instances
from apps.vpn.services.dtos import VPNReissueOut
from apps.vpn.services.reissue_vpn_subscription_service import (
    ReissueVPNSubscriptionService,
)
from apps.vpn.services.schedule_profiles_service import ScheduleProfilesService
from apps.vpn.tests.factories import VPNInstanceFactory, VPNSubscriptionFactory


class TestReissueVPNSubscriptionView(APITestCase):
    url = "/api/v1/vpn/reissue/"

    def _post(self, data: dict[str, str]) -> object:
        return self.client.post(
            self.url,
            data=data,
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

    def test_requires_valid_bot_authentication(self) -> None:
        """Catches an endpoint that permits a reissue without valid bot auth."""
        for headers in ({}, {"Bot-Auth-Token": "invalid-bot-auth-token"}):
            with self.subTest(headers=headers):
                response = self.client.post(self.url, data={"username": "12345678"}, headers=headers)

                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("apps.vpn.api.v1.views.reissue_views.get_reissue_vpn_subscription_service")
    def test_passes_form_username_to_reissue_service(self, get_reissue_service: Mock) -> None:
        """Catches a view that reads a different transport field than username."""
        get_reissue_service.return_value.return_value = VPNReissueOut(
            expired_at=timezone.now(),
            subscription_url="https://dash.example.com/api/v1/vpn/subscriptions/new-token/",
        )

        response = self._post({"username": "12345678"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        get_reissue_service.return_value.assert_called_once_with(username="12345678")

    @patch("apps.vpn.api.v1.views.reissue_views.get_reissue_vpn_subscription_service")
    def test_returns_unavailable_domain_error_from_existing_handler(
        self,
        get_reissue_service: Mock,
    ) -> None:
        """Catches a view that leaks unavailable reissue errors as non-400 responses."""
        get_reissue_service.return_value.side_effect = VPNReissueUnavailable(telegram_id="12345678")

        response = self._post({"username": "12345678"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                "error": "🔒 Перевыпуск VPN-ссылки доступен только после продления подписки.",
                "detail": {},
            },
        )

    @patch("apps.vpn.api.v1.views.reissue_views.get_reissue_vpn_subscription_service")
    def test_returns_cooldown_domain_error_from_existing_handler(
        self,
        get_reissue_service: Mock,
    ) -> None:
        """Catches a view that changes the five-minute cooldown response semantics."""
        get_reissue_service.return_value.side_effect = VPNReissueCooldown(telegram_id="12345678")

        response = self._post({"username": "12345678"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                "error": "🔒 Пожалуйста, подождите 5 минут с последнего обновления.",
                "detail": {},
            },
        )

    @patch("apps.vpn.api.v1.views.reissue_views.get_reissue_vpn_subscription_service")
    def test_rotates_subscription_and_exposes_only_reissue_dto_fields(
        self,
        get_reissue_service: Mock,
    ) -> None:
        """Catches a route that leaves the old URL valid or returns credentials."""
        user = SystemUserFactory(username="12345678")
        subscription = VPNSubscriptionFactory(
            user=user,
            token="old-subscription-token",
            vless_uuid="11111111-2222-3333-4444-555555555555",
            hysteria_secret="old-hysteria-secret",
        )
        active_instance = VPNInstanceFactory(name="Moscow", public_host="vpn.example.com")
        VPNInstanceFactory(is_active=False)
        delayed_put = Mock()
        scheduler = ScheduleProfilesService(
            get_active_instances=get_active_vpn_instances,
            get_active_subscriptions=lambda: [],
            enqueue_delivery=delayed_put,
        )
        reissue_service = ReissueVPNSubscriptionService(
            generate_token=lambda: "new-subscription-token",
            generate_vless_uuid=lambda: UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
            generate_hysteria_secret=lambda: "new-hysteria-secret",
            schedule_profiles=scheduler,
            subscription_base_url=settings.VPN_SUBSCRIPTION_BASE_URL,
        )
        get_reissue_service.return_value = reissue_service

        with self.captureOnCommitCallbacks(execute=True):
            response = self._post({"username": user.username})

        subscription.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "expired_at": subscription.expired_at.isoformat().replace("+00:00", "Z"),
                "subscription_url": (
                    f"{settings.VPN_SUBSCRIPTION_BASE_URL.rstrip('/')}"
                    "/api/v1/vpn/subscriptions/new-subscription-token/"
                ),
            },
        )
        self.assertEqual(set(response.json()), {"expired_at", "subscription_url"})
        self.assertEqual(subscription.token, "new-subscription-token")
        self.assertEqual(str(subscription.vless_uuid), "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        self.assertEqual(subscription.hysteria_secret, "new-hysteria-secret")
        delayed_put.assert_called_once_with(
            subscription_id=subscription.pk,
            instance_id=active_instance.pk,
            operation="put",
        )

        old_response = self.client.get("/api/v1/vpn/subscriptions/old-subscription-token/")
        new_response = self.client.get("/api/v1/vpn/subscriptions/new-subscription-token/")

        self.assertEqual(old_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(new_response.status_code, status.HTTP_200_OK)
        profiles = b64decode(new_response.content).decode("utf-8")
        self.assertIn("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", profiles)
        self.assertIn("new-hysteria-secret", profiles)
