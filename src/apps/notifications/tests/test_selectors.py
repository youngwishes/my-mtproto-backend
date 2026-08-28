from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.notifications.enums import FilterType
from apps.notifications.selectors import (
    get_mailing_by_id,
    get_mtproto_link_reissue_recipients,
    get_template,
    get_users_by_filter,
)
from apps.notifications.tests.factories import MailingFactory, NotificationTemplateFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
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
        VDSInstanceFactory()
        user_expiring = SystemUserFactory()
        user_safe = SystemUserFactory()
        MTPRotoKeyFactory(
            user=user_expiring,
            expired_date=timezone.now() + timedelta(hours=12),
            was_deleted=False,
        )
        MTPRotoKeyFactory(
            user=user_safe,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
        )
        result = get_users_by_filter(
            filter_type=FilterType.EXPIRING_SOON,
            params={"days_until_expiry": 1},
        )
        self.assertEqual(list(result.values_list("pk", flat=True)), [user_expiring.pk])


class TestGetMTPRotoLinkReissueRecipients(TestCase):
    def setUp(self) -> None:
        self.now = timezone.now()

    def test_returns_each_user_with_a_current_key_once(self) -> None:
        user_with_multiple_keys = SystemUserFactory(is_active=False)
        user_with_one_key = SystemUserFactory()
        MTPRotoKeyFactory(
            user=user_with_multiple_keys,
            expired_date=self.now + timedelta(days=1),
        )
        MTPRotoKeyFactory(
            user=user_with_multiple_keys,
            expired_date=self.now + timedelta(days=2),
        )
        MTPRotoKeyFactory(
            user=user_with_one_key,
            expired_date=self.now + timedelta(days=1),
        )

        with mock.patch("apps.notifications.selectors.timezone.now", return_value=self.now):
            result = get_mtproto_link_reissue_recipients()

        self.assertEqual(
            list(result.order_by("pk").values_list("pk", flat=True)),
            [user_with_multiple_keys.pk, user_with_one_key.pk],
        )

    def test_excludes_users_without_a_key_matching_every_condition(self) -> None:
        excluded_users = [SystemUserFactory() for _ in range(5)]
        MTPRotoKeyFactory(
            user=excluded_users[0],
            is_active=False,
            expired_date=self.now + timedelta(days=1),
        )
        MTPRotoKeyFactory(
            user=excluded_users[1],
            was_deleted=True,
            expired_date=self.now + timedelta(days=1),
        )
        MTPRotoKeyFactory(
            user=excluded_users[2],
            expired_date=self.now - timedelta(microseconds=1),
        )
        MTPRotoKeyFactory(user=excluded_users[3], expired_date=self.now)
        MTPRotoKeyFactory(user=excluded_users[4], expired_date=None)

        with mock.patch("apps.notifications.selectors.timezone.now", return_value=self.now):
            result = get_mtproto_link_reissue_recipients()

        self.assertEqual(list(result), [])

    def test_does_not_combine_conditions_from_different_keys(self) -> None:
        user = SystemUserFactory()
        MTPRotoKeyFactory(
            user=user,
            is_active=False,
            was_deleted=False,
            expired_date=self.now + timedelta(days=1),
        )
        MTPRotoKeyFactory(
            user=user,
            is_active=True,
            was_deleted=True,
            expired_date=self.now + timedelta(days=1),
        )
        MTPRotoKeyFactory(
            user=user,
            is_active=True,
            was_deleted=False,
            expired_date=self.now,
        )

        with mock.patch("apps.notifications.selectors.timezone.now", return_value=self.now):
            result = get_mtproto_link_reissue_recipients()

        self.assertEqual(list(result), [])

    def test_does_not_change_keys(self) -> None:
        MTPRotoKeyFactory(expired_date=self.now + timedelta(days=1))
        before = list(MTPRotoKey.objects.order_by("pk").values())

        with mock.patch("apps.notifications.selectors.timezone.now", return_value=self.now):
            list(get_mtproto_link_reissue_recipients())

        self.assertEqual(list(MTPRotoKey.objects.order_by("pk").values()), before)
