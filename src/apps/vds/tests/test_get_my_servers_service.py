from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from apps.vds.exceptions import KeyDoesNotExist
from apps.vds.models import MTPRotoKey
from apps.vds.services.get_my_servers_service import get_my_servers_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory
from apps.users.models import SystemUser
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
            token="testtoken",
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
            expired_date=timezone.now() + timedelta(days=30),
            is_active=True,
            was_deleted=False,
        )

        result = self.service(username="22222222")

        self.assertEqual(len(result.servers), 1)
        self.assertEqual(result.servers[0].location, "🇳🇱 Нидерланды")

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_auto_activates_free_period_for_new_user(self, mock_push, mock_log) -> None:
        # Новый пользователь жмёт «Мои серверы» → бесплатный период активируется
        # на 30 дней, и сразу возвращается список серверов.
        VDSInstanceFactory(name="nl1", location="🇳🇱 Нидерланды", is_active=True)

        result = self.service(username="nonexistent")

        user = SystemUser.objects.get(username="nonexistent")
        self.assertTrue(user.first_month_free_used)
        self.assertEqual(MTPRotoKey.objects.filter(user=user).count(), 1)
        key = MTPRotoKey.objects.get(user=user)
        self.assertEqual(key.expired_date.date(), (timezone.now() + timedelta(days=30)).date())
        self.assertEqual(result.expired_date, key.expired_date.date().strftime("%d.%m.%y"))
        self.assertEqual(len(result.servers), 1)
        mock_push.assert_called_once_with(key_id=key.pk)

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_auto_activates_when_user_has_no_active_key(self, mock_push, mock_log) -> None:
        user = SystemUserFactory(username="33333333", first_month_free_used=False)
        VDSInstanceFactory(is_active=True)

        result = self.service(username="33333333")

        user.refresh_from_db()
        self.assertTrue(user.first_month_free_used)
        self.assertEqual(MTPRotoKey.objects.filter(user=user).count(), 1)
        self.assertEqual(len(result.servers), 1)
        mock_push.assert_called_once()

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_auto_activates_when_existing_key_expired(self, mock_push, mock_log) -> None:
        # Истёкший ключ + период ещё не использован → выдаётся свежий 30-дневный ключ.
        user = SystemUserFactory(username="44444444", first_month_free_used=False)
        VDSInstanceFactory(is_active=True)
        MTPRotoKeyFactory(
            user=user,
            expired_date=timezone.now() - timedelta(days=1),
            is_active=True,
            was_deleted=False,
        )

        result = self.service(username="44444444")

        user.refresh_from_db()
        self.assertTrue(user.first_month_free_used)
        key = MTPRotoKey.objects.get(user=user)
        self.assertEqual(key.expired_date.date(), (timezone.now() + timedelta(days=30)).date())
        self.assertEqual(len(result.servers), 1)
        mock_push.assert_called_once_with(key_id=key.pk)

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_raises_when_free_already_used_and_no_active_key(self, mock_push, mock_log) -> None:
        # Период уже израсходован, ключ истёк → повторной авто-активации нет.
        user = SystemUserFactory(username="55555555", first_month_free_used=True)
        VDSInstanceFactory(is_active=True)

        with self.assertRaises(KeyDoesNotExist):
            self.service(username="55555555")

        self.assertEqual(MTPRotoKey.objects.filter(user=user).count(), 0)
        mock_push.assert_not_called()
