# src/apps/notifications/tests/test_selectors.py
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.notifications.enums import FilterType
from apps.notifications.selectors import get_mailing_by_id, get_template, get_users_by_filter
from apps.notifications.tests.factories import MailingFactory, NotificationTemplateFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestGetTemplate(TestCase):
    def test_returns_active_template_by_slug(self) -> None:
        template = NotificationTemplateFactory(slug="test-slug")
        result = get_template(slug="test-slug")
        self.assertEqual(result.pk, template.pk)

    def test_raises_for_inactive_template(self) -> None:
        NotificationTemplateFactory(slug="inactive", is_active=False)
        from apps.notifications.models import NotificationTemplate
        with self.assertRaises(NotificationTemplate.DoesNotExist):
            get_template(slug="inactive")

    def test_raises_for_nonexistent_slug(self) -> None:
        from apps.notifications.models import NotificationTemplate
        with self.assertRaises(NotificationTemplate.DoesNotExist):
            get_template(slug="nonexistent")


class TestGetMailingById(TestCase):
    def test_returns_mailing_with_template(self) -> None:
        mailing = MailingFactory()
        result = get_mailing_by_id(mailing_id=mailing.pk)
        self.assertEqual(result.pk, mailing.pk)
        self.assertEqual(result.template.pk, mailing.template.pk)


class TestGetUsersByFilter(TestCase):
    def test_all_active_returns_active_users(self) -> None:
        user1 = SystemUserFactory(is_active=True)
        user2 = SystemUserFactory(is_active=True)
        SystemUserFactory(is_active=False)
        result = get_users_by_filter(filter_type=FilterType.ALL_ACTIVE, params={})
        self.assertEqual(set(result.values_list("pk", flat=True)), {user1.pk, user2.pk})

    def test_expiring_soon_returns_users_with_expiring_keys(self) -> None:
        vds = VDSInstanceFactory()
        user_expiring = SystemUserFactory()
        user_safe = SystemUserFactory()
        MTPRotoKeyFactory(
            user=user_expiring, vds=vds,
            expired_date=timezone.now() + timedelta(hours=12),
            was_deleted=False,
        )
        MTPRotoKeyFactory(
            user=user_safe, vds=vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
        )
        result = get_users_by_filter(
            filter_type=FilterType.EXPIRING_SOON,
            params={"days_until_expiry": 1},
        )
        self.assertEqual(list(result.values_list("pk", flat=True)), [user_expiring.pk])
