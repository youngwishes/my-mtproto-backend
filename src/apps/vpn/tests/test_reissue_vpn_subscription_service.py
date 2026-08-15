from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vpn.exceptions import VPNReissueCooldown, VPNReissueUnavailable
from apps.vpn.models import _generate_hysteria_secret, _generate_subscription_token
from apps.vpn.services import (
    ReissueVPNSubscriptionService,
    get_reissue_vpn_subscription_service,
)
from apps.vpn.services.dtos import VPNReissueOut
from apps.vpn.tests.factories import VPNSubscriptionFactory


class TestReissueVPNSubscriptionService(TestCase):
    def test_rotates_credentials_preserves_subscription_and_schedules_after_commit(self) -> None:
        """Catches a reissue that leaves a credential stable or schedules node delivery early."""
        user = SystemUserFactory(username="1487189460")
        subscription = VPNSubscriptionFactory(
            user=user,
            token="old-subscription-token",
            vless_uuid="11111111-1111-1111-1111-111111111111",
            hysteria_secret="old-hysteria-secret",
        )
        schedule_profiles = Mock()
        service = ReissueVPNSubscriptionService(
            generate_token=lambda: "new-subscription-token",
            generate_vless_uuid=lambda: UUID("22222222-2222-2222-2222-222222222222"),
            generate_hysteria_secret=lambda: "new-hysteria-secret",
            schedule_profiles=schedule_profiles,
            subscription_base_url="https://dash.example.com/",
        )
        expired_at = subscription.expired_at
        is_active = subscription.is_active
        before_reissue = timezone.now()

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            result = service(username=user.username)
            schedule_profiles.assert_not_called()

        subscription.refresh_from_db()
        self.assertEqual(subscription.token, "new-subscription-token")
        self.assertEqual(
            str(subscription.vless_uuid),
            "22222222-2222-2222-2222-222222222222",
        )
        self.assertEqual(subscription.hysteria_secret, "new-hysteria-secret")
        self.assertEqual(subscription.expired_at, expired_at)
        self.assertEqual(subscription.is_active, is_active)
        self.assertGreaterEqual(subscription.last_reissued_at, before_reissue)
        self.assertEqual(result.expired_at, expired_at)
        self.assertEqual(
            result.subscription_url,
            "https://dash.example.com/api/v1/vpn/subscriptions/new-subscription-token/",
        )
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        schedule_profiles.assert_called_once_with(subscription_id=subscription.pk)

    def test_missing_user_is_unavailable_without_scheduling(self) -> None:
        """Catches a reissue that creates or changes state for an unknown user."""
        schedule_profiles = Mock()
        service = ReissueVPNSubscriptionService(
            generate_token=lambda: "new-subscription-token",
            generate_vless_uuid=lambda: UUID("22222222-2222-2222-2222-222222222222"),
            generate_hysteria_secret=lambda: "new-hysteria-secret",
            schedule_profiles=schedule_profiles,
            subscription_base_url="https://dash.example.com/",
        )

        with self.assertRaises(VPNReissueUnavailable) as caught:
            service(username="missing-user", notify_on_error=False)

        self.assertEqual(
            caught.exception.message,
            "🔒 Перевыпуск VPN-ссылки доступен только после продления подписки.",
        )
        self.assertEqual(caught.exception.context, {})
        schedule_profiles.assert_not_called()

    def test_missing_subscription_is_unavailable_without_scheduling(self) -> None:
        """Catches a reissue that creates credentials when the user has no subscription."""
        user = SystemUserFactory(username="without-subscription")
        schedule_profiles = Mock()
        service = ReissueVPNSubscriptionService(
            generate_token=lambda: "new-subscription-token",
            generate_vless_uuid=lambda: UUID("22222222-2222-2222-2222-222222222222"),
            generate_hysteria_secret=lambda: "new-hysteria-secret",
            schedule_profiles=schedule_profiles,
            subscription_base_url="https://dash.example.com/",
        )

        with self.assertRaises(VPNReissueUnavailable):
            service(username=user.username, notify_on_error=False)

        schedule_profiles.assert_not_called()

    def test_inactive_subscription_is_unavailable_without_mutation(self) -> None:
        """Catches a reissue that rotates credentials for an inactive subscription."""
        user = SystemUserFactory(username="inactive-subscription")
        subscription = VPNSubscriptionFactory(
            user=user,
            token="old-subscription-token",
            vless_uuid="11111111-1111-1111-1111-111111111111",
            hysteria_secret="old-hysteria-secret",
            is_active=False,
        )
        schedule_profiles = Mock()
        service = ReissueVPNSubscriptionService(
            generate_token=lambda: "new-subscription-token",
            generate_vless_uuid=lambda: UUID("22222222-2222-2222-2222-222222222222"),
            generate_hysteria_secret=lambda: "new-hysteria-secret",
            schedule_profiles=schedule_profiles,
            subscription_base_url="https://dash.example.com/",
        )

        with self.assertRaises(VPNReissueUnavailable):
            service(username=user.username, notify_on_error=False)

        subscription.refresh_from_db()
        self.assertEqual(subscription.token, "old-subscription-token")
        self.assertEqual(
            str(subscription.vless_uuid),
            "11111111-1111-1111-1111-111111111111",
        )
        self.assertEqual(subscription.hysteria_secret, "old-hysteria-secret")
        self.assertIsNone(subscription.last_reissued_at)
        schedule_profiles.assert_not_called()

    def test_expired_subscription_is_unavailable_without_mutation(self) -> None:
        """Catches a reissue that rotates credentials after subscription expiry."""
        user = SystemUserFactory(username="expired-subscription")
        subscription = VPNSubscriptionFactory(
            user=user,
            token="old-subscription-token",
            vless_uuid="11111111-1111-1111-1111-111111111111",
            hysteria_secret="old-hysteria-secret",
            expired_at=timezone.now() - timedelta(seconds=1),
        )
        schedule_profiles = Mock()
        service = ReissueVPNSubscriptionService(
            generate_token=lambda: "new-subscription-token",
            generate_vless_uuid=lambda: UUID("22222222-2222-2222-2222-222222222222"),
            generate_hysteria_secret=lambda: "new-hysteria-secret",
            schedule_profiles=schedule_profiles,
            subscription_base_url="https://dash.example.com/",
        )

        with self.assertRaises(VPNReissueUnavailable):
            service(username=user.username, notify_on_error=False)

        subscription.refresh_from_db()
        self.assertEqual(subscription.token, "old-subscription-token")
        self.assertEqual(
            str(subscription.vless_uuid),
            "11111111-1111-1111-1111-111111111111",
        )
        self.assertEqual(subscription.hysteria_secret, "old-hysteria-secret")
        self.assertIsNone(subscription.last_reissued_at)
        schedule_profiles.assert_not_called()

    def test_rejects_reissue_inside_cooldown_with_exact_message(self) -> None:
        """Catches a cooldown that permits early credential rotation or changes its user message."""
        user = SystemUserFactory(username="cooldown-subscription")
        subscription = VPNSubscriptionFactory(
            user=user,
            token="old-subscription-token",
            vless_uuid="11111111-1111-1111-1111-111111111111",
            hysteria_secret="old-hysteria-secret",
            last_reissued_at=timezone.now() - timedelta(minutes=4, seconds=59),
        )
        schedule_profiles = Mock()
        service = ReissueVPNSubscriptionService(
            generate_token=lambda: "new-subscription-token",
            generate_vless_uuid=lambda: UUID("22222222-2222-2222-2222-222222222222"),
            generate_hysteria_secret=lambda: "new-hysteria-secret",
            schedule_profiles=schedule_profiles,
            subscription_base_url="https://dash.example.com/",
        )

        with self.assertRaises(VPNReissueCooldown) as caught:
            service(username=user.username, notify_on_error=False)

        self.assertEqual(
            caught.exception.message,
            "🔒 Пожалуйста, подождите 5 минут с последнего обновления.",
        )
        self.assertEqual(caught.exception.context, {})
        subscription.refresh_from_db()
        self.assertEqual(subscription.token, "old-subscription-token")
        self.assertEqual(
            str(subscription.vless_uuid),
            "11111111-1111-1111-1111-111111111111",
        )
        self.assertEqual(subscription.hysteria_secret, "old-hysteria-secret")
        schedule_profiles.assert_not_called()

    def test_accepts_reissue_at_five_minute_cooldown_boundary(self) -> None:
        """Catches a cooldown that rejects the allowed five-minute boundary."""
        user = SystemUserFactory(username="cooldown-boundary-subscription")
        now = timezone.now()
        subscription = VPNSubscriptionFactory(
            user=user,
            last_reissued_at=now - timedelta(minutes=5),
        )
        schedule_profiles = Mock()
        service = ReissueVPNSubscriptionService(
            generate_token=lambda: "new-subscription-token",
            generate_vless_uuid=lambda: UUID("22222222-2222-2222-2222-222222222222"),
            generate_hysteria_secret=lambda: "new-hysteria-secret",
            schedule_profiles=schedule_profiles,
            subscription_base_url="https://dash.example.com/",
        )

        with (
            patch(
                "apps.vpn.services.reissue_vpn_subscription_service.timezone.now",
                return_value=now,
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            service(username=user.username)

        subscription.refresh_from_db()
        self.assertEqual(subscription.token, "new-subscription-token")
        schedule_profiles.assert_called_once_with(subscription_id=subscription.pk)


class TestReissueVPNSubscriptionServiceFactory(TestCase):
    @override_settings(VPN_SUBSCRIPTION_BASE_URL="https://dash.example.com")
    @patch("apps.vpn.services.reissue_vpn_subscription_service.get_schedule_profiles_service")
    def test_wires_existing_generators_scheduler_base_url_and_public_dto(
        self,
        get_schedule_profiles_service: Mock,
    ) -> None:
        """Catches a factory that bypasses VPN model generators or hides its public contract."""
        scheduler = Mock()
        get_schedule_profiles_service.return_value = scheduler

        service = get_reissue_vpn_subscription_service()

        self.assertIs(service.generate_token, _generate_subscription_token)
        self.assertIs(service.generate_vless_uuid, uuid4)
        self.assertIs(service.generate_hysteria_secret, _generate_hysteria_secret)
        self.assertIs(service.schedule_profiles, scheduler)
        self.assertEqual(service.subscription_base_url, "https://dash.example.com")
        self.assertEqual(
            set(VPNReissueOut.__dataclass_fields__),
            {"expired_at", "subscription_url"},
        )
