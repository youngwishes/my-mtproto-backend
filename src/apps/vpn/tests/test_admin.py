from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.vpn.admin import VPNInstanceAdmin
from apps.vpn.models import VPNInstance
from apps.vpn.tasks import deliver_vpn_profile_task
from apps.vpn.tests.factories import VPNInstanceFactory, VPNSubscriptionFactory


class TestVPNInstanceAdmin(TestCase):
    def setUp(self) -> None:
        self.admin = VPNInstanceAdmin(VPNInstance, AdminSite())
        self.request = RequestFactory().post("/admin/apps/vpn/vpninstance/")
        SessionMiddleware(lambda request: None).process_request(self.request)
        setattr(self.request, "_messages", FallbackStorage(self.request))

    def test_new_node_is_saved_inactive_until_admin_manually_activates_it(self) -> None:
        instance = VPNInstanceFactory.build(is_active=True)

        self.admin.save_model(self.request, instance, form=None, change=False)

        instance.refresh_from_db()
        self.assertFalse(instance.is_active)

    def test_backfill_repeatably_enqueues_current_active_profiles_for_selected_inactive_node(
        self,
    ) -> None:
        instance = VPNInstanceFactory(is_active=False)
        active = VPNSubscriptionFactory(expired_at=timezone.now() + timedelta(days=1))
        VPNSubscriptionFactory(is_active=False, expired_at=timezone.now() + timedelta(days=1))
        VPNSubscriptionFactory(expired_at=timezone.now() - timedelta(seconds=1))

        with patch.object(deliver_vpn_profile_task, "delay") as delay:
            self.admin.backfill_profiles(
                self.request,
                VPNInstance.objects.filter(pk=instance.pk),
            )
            self.admin.backfill_profiles(
                self.request,
                VPNInstance.objects.filter(pk=instance.pk),
            )

        self.assertEqual(delay.call_count, 2)
        delay.assert_called_with(
            subscription_id=active.pk,
            instance_id=instance.pk,
            operation="put",
        )

    def test_backfill_rejects_active_or_multiple_selected_nodes(
        self,
    ) -> None:
        active = VPNInstanceFactory(is_active=True)
        inactive = VPNInstanceFactory(is_active=False)

        with patch.object(deliver_vpn_profile_task, "delay") as delay:
            self.admin.backfill_profiles(
                self.request,
                VPNInstance.objects.filter(pk=active.pk),
            )
            self.admin.backfill_profiles(
                self.request,
                VPNInstance.objects.filter(pk__in=[active.pk, inactive.pk]),
            )

        delay.assert_not_called()
