from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from apps.vds.exceptions import KeyDoesNotExist
from apps.vds.services.get_my_servers_service import get_my_servers_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory
from apps.users.tests.factories import SystemUserFactory


@mock.patch("apps.core.decorators._log_service_error")
class TestGetMyServersService(TestCase):
    def setUp(self) -> None:
        self.service = get_my_servers_service()

    def test_returns_all_active_vds_links_for_user_with_key(self, mock_log) -> None:
        user = SystemUserFactory(username="11111111")
        vds1 = VDSInstanceFactory(name="nl1", location="🇳🇱 Нидерланды", is_active=True)
        vds2 = VDSInstanceFactory(name="de1", location="🇩🇪 Германия", is_active=True)
        key = MTPRotoKeyFactory(
            user=user,
            vds=vds1,
            token="testtoken",
            tls_domain="petrovich.ru",
            expired_date=timezone.now() + timedelta(days=30),
            is_active=True,
            was_deleted=False,
        )

        result = self.service(username="11111111")

        self.assertEqual(result.expired_date, key.expired_date.date().strftime("%d.%m.%y"))
        self.assertEqual(len(result.servers), 2)
        locations = [s.location for s in result.servers]
        self.assertIn("🇳🇱 Нидерланды", locations)
        self.assertIn("🇩🇪 Германия", locations)
        for server in result.servers:
            self.assertIn("tg://proxy?server=", server.proxy_link)
            self.assertIn(".beatvault.ru", server.proxy_link)
            domain_hex = settings.TLS_DOMAIN.encode("utf-8").hex()
            self.assertIn(f"eetesttoken{domain_hex}", server.proxy_link)

    def test_excludes_inactive_vds(self, mock_log) -> None:
        user = SystemUserFactory(username="22222222")
        vds1 = VDSInstanceFactory(name="nl1", location="🇳🇱 Нидерланды", is_active=True)
        VDSInstanceFactory(name="de1", location="🇩🇪 Германия", is_active=False)
        MTPRotoKeyFactory(
            user=user,
            vds=vds1,
            expired_date=timezone.now() + timedelta(days=30),
            is_active=True,
            was_deleted=False,
        )

        result = self.service(username="22222222")

        self.assertEqual(len(result.servers), 1)
        self.assertEqual(result.servers[0].location, "🇳🇱 Нидерланды")

    def test_raises_when_user_not_found(self, mock_log) -> None:
        with self.assertRaises(KeyDoesNotExist):
            self.service(username="nonexistent")

    def test_raises_when_user_has_no_active_key(self, mock_log) -> None:
        user = SystemUserFactory(username="33333333")
        VDSInstanceFactory(is_active=True)

        with self.assertRaises(KeyDoesNotExist):
            self.service(username="33333333")

    def test_raises_when_key_is_expired(self, mock_log) -> None:
        user = SystemUserFactory(username="44444444")
        vds = VDSInstanceFactory(is_active=True)
        MTPRotoKeyFactory(
            user=user,
            vds=vds,
            expired_date=timezone.now() - timedelta(days=1),
            is_active=True,
            was_deleted=False,
        )

        with self.assertRaises(KeyDoesNotExist):
            self.service(username="44444444")
