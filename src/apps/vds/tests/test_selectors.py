from __future__ import annotations

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.selectors import (
    get_active_broadcast_keys,
    get_active_key,
    get_all_active_vds_instances,
    get_keys_by_username,
    get_keys_expired_up_to_date,
    get_keys_expiring_on_date,
    get_least_populated_vds,
    get_other_active_vds_instances,
    get_unnotified_keys_expiring_on_date,
    get_vds_instance_by_id,
    get_vds_instance_keys,
)
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestGetActiveKey(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()

    def test_returns_active_key(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
        )
        result = get_active_key(user=self.user)
        self.assertEqual(result, key)

    def test_returns_none_when_no_key(self) -> None:
        result = get_active_key(user=self.user)
        self.assertIsNone(result)

    def test_returns_none_when_key_expired(self) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() - timedelta(days=1),
            was_deleted=False,
        )
        result = get_active_key(user=self.user)
        self.assertIsNone(result)

    def test_returns_none_when_key_deleted(self) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=True,
        )
        result = get_active_key(user=self.user)
        self.assertIsNone(result)

    def test_returns_none_when_key_inactive(self) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
            is_active=False,
        )
        result = get_active_key(user=self.user)
        self.assertIsNone(result)


class TestGetLeastPopulatedVds(TestCase):
    def test_returns_vds_with_fewest_active_keys(self) -> None:
        vds_busy = VDSInstanceFactory()
        vds_free = VDSInstanceFactory()

        user1 = SystemUserFactory()
        user2 = SystemUserFactory()

        MTPRotoKeyFactory(vds=vds_busy, user=user1)
        MTPRotoKeyFactory(vds=vds_busy, user=user2)
        MTPRotoKeyFactory(vds=vds_free, user=SystemUserFactory())

        result = get_least_populated_vds()
        self.assertEqual(result, vds_free)

    def test_returns_none_when_no_vds(self) -> None:
        result = get_least_populated_vds()
        self.assertIsNone(result)


class TestGetAllActiveVdsInstances(TestCase):
    def test_returns_active_instances(self) -> None:
        active = VDSInstanceFactory(is_active=True)
        VDSInstanceFactory(is_active=False)
        result = get_all_active_vds_instances()
        self.assertEqual(list(result), [active])

    def test_returns_empty_when_no_instances(self) -> None:
        result = get_all_active_vds_instances()
        self.assertFalse(result.exists())


class TestGetKeysByUsername(TestCase):
    def test_returns_keys_for_given_username(self) -> None:
        user = SystemUserFactory(username="target_user")
        vds = VDSInstanceFactory()
        key1 = MTPRotoKeyFactory(user=user, vds=vds)
        key2 = MTPRotoKeyFactory(user=user, vds=vds)

        # Another user's key should not appear
        other_user = SystemUserFactory(username="other_user")
        MTPRotoKeyFactory(user=other_user, vds=vds)

        result = get_keys_by_username(username="target_user")
        self.assertEqual(set(result), {key1, key2})

    def test_returns_empty_queryset_for_unknown_username(self) -> None:
        result = get_keys_by_username(username="nonexistent_user")
        self.assertFalse(result.exists())


class TestGetKeysExpiringOnDate(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()
        self.target_date = date(2026, 7, 1)

    def test_returns_keys_expiring_on_given_date(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.make_aware(
                timezone.datetime(2026, 7, 1, 12, 0, 0),
            ),
            was_deleted=False,
            is_active=True,
        )
        result = get_keys_expiring_on_date(date=self.target_date)
        self.assertIn(key, result)

    def test_excludes_deleted_keys(self) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.make_aware(
                timezone.datetime(2026, 7, 1, 12, 0, 0),
            ),
            was_deleted=True,
            is_active=True,
        )
        result = get_keys_expiring_on_date(date=self.target_date)
        self.assertFalse(result.exists())

    def test_excludes_inactive_keys(self) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.make_aware(
                timezone.datetime(2026, 7, 1, 12, 0, 0),
            ),
            was_deleted=False,
            is_active=False,
        )
        result = get_keys_expiring_on_date(date=self.target_date)
        self.assertFalse(result.exists())

    def test_excludes_keys_expiring_on_other_dates(self) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.make_aware(
                timezone.datetime(2026, 7, 2, 12, 0, 0),
            ),
            was_deleted=False,
            is_active=True,
        )
        result = get_keys_expiring_on_date(date=self.target_date)
        self.assertFalse(result.exists())


class TestGetKeysExpiredUpToDate(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()
        self.target_date = date(2026, 7, 1)

    def test_includes_keys_expired_on_date(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.make_aware(
                timezone.datetime(2026, 7, 1, 12, 0, 0),
            ),
            was_deleted=False,
            is_active=True,
        )
        result = get_keys_expired_up_to_date(date=self.target_date)
        self.assertIn(key, result)

    def test_includes_keys_expired_before_date(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.make_aware(
                timezone.datetime(2026, 6, 30, 12, 0, 0),
            ),
            was_deleted=False,
            is_active=True,
        )
        result = get_keys_expired_up_to_date(date=self.target_date)
        self.assertIn(key, result)

    def test_excludes_keys_expiring_after_date(self) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.make_aware(
                timezone.datetime(2026, 7, 2, 12, 0, 0),
            ),
            was_deleted=False,
            is_active=True,
        )
        result = get_keys_expired_up_to_date(date=self.target_date)
        self.assertFalse(result.exists())


class TestGetUnnotifiedKeysExpiringOnDate(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()
        self.target_date = date(2026, 7, 1)

    def test_returns_unnotified_keys(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.make_aware(
                timezone.datetime(2026, 7, 1, 12, 0, 0),
            ),
            was_deleted=False,
            is_active=True,
            user_notified=False,
        )
        result = get_unnotified_keys_expiring_on_date(date=self.target_date)
        self.assertIn(key, result)

    def test_excludes_already_notified_keys(self) -> None:
        MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.make_aware(
                timezone.datetime(2026, 7, 1, 12, 0, 0),
            ),
            was_deleted=False,
            is_active=True,
            user_notified=True,
        )
        result = get_unnotified_keys_expiring_on_date(date=self.target_date)
        self.assertFalse(result.exists())


class TestGetVdsInstanceById(TestCase):
    def test_returns_instance(self) -> None:
        vds = VDSInstanceFactory()
        result = get_vds_instance_by_id(pk=vds.pk)
        self.assertEqual(result, vds)

    def test_raises_on_missing_instance(self) -> None:
        from apps.vds.models import VDSInstance

        with self.assertRaises(VDSInstance.DoesNotExist):
            get_vds_instance_by_id(pk=99999)


class TestGetOtherActiveVdsInstances(TestCase):
    def test_excludes_given_instance(self) -> None:
        vds_1 = VDSInstanceFactory(is_active=True)
        vds_2 = VDSInstanceFactory(is_active=True)
        result = get_other_active_vds_instances(exclude_pk=vds_1.pk)
        self.assertEqual(list(result), [vds_2])

    def test_excludes_inactive_instances(self) -> None:
        active = VDSInstanceFactory(is_active=True)
        VDSInstanceFactory(is_active=False)
        excluded = VDSInstanceFactory(is_active=True)
        result = get_other_active_vds_instances(exclude_pk=excluded.pk)
        self.assertEqual(list(result), [active])

    def test_returns_empty_when_only_excluded_instance(self) -> None:
        vds = VDSInstanceFactory(is_active=True)
        result = get_other_active_vds_instances(exclude_pk=vds.pk)
        self.assertFalse(result.exists())


class TestGetVdsInstanceKeys(TestCase):
    def test_returns_keys_for_instance(self) -> None:
        vds = VDSInstanceFactory()
        other_vds = VDSInstanceFactory()
        key = MTPRotoKeyFactory(vds=vds)
        MTPRotoKeyFactory(vds=other_vds)
        result = get_vds_instance_keys(instance=vds)
        self.assertEqual(list(result), [key])

    def test_returns_empty_for_instance_without_keys(self) -> None:
        vds = VDSInstanceFactory()
        result = get_vds_instance_keys(instance=vds)
        self.assertFalse(result.exists())

    def test_select_related_user(self) -> None:
        vds = VDSInstanceFactory()
        MTPRotoKeyFactory(vds=vds)
        keys = list(get_vds_instance_keys(instance=vds))
        with self.assertNumQueries(0):
            for key in keys:
                _ = key.user.username


class TestGetActiveBroadcastKeys(TestCase):
    def setUp(self) -> None:
        self.vds = VDSInstanceFactory()

    def test_returns_active_paid_keys(self) -> None:
        user = SystemUserFactory(first_month_free_used=True)
        key = MTPRotoKeyFactory(
            user=user,
            vds=self.vds,
            is_active=True,
            was_deleted=False,
            expired_date=timezone.now() + timedelta(days=10),
        )
        result = get_active_broadcast_keys(testing=False)
        self.assertIn(key, result)

    def test_excludes_expired_deleted_inactive_keys(self) -> None:
        user = SystemUserFactory(first_month_free_used=True)

        # expired
        MTPRotoKeyFactory(
            user=user,
            vds=self.vds,
            is_active=True,
            was_deleted=False,
            expired_date=timezone.now() - timedelta(days=1),
        )
        # deleted
        MTPRotoKeyFactory(
            user=user,
            vds=self.vds,
            is_active=True,
            was_deleted=True,
            expired_date=timezone.now() + timedelta(days=10),
        )
        # inactive
        MTPRotoKeyFactory(
            user=user,
            vds=self.vds,
            is_active=False,
            was_deleted=False,
            expired_date=timezone.now() + timedelta(days=10),
        )

        result = get_active_broadcast_keys(testing=False)
        self.assertFalse(result.exists())

    def test_testing_mode_returns_only_test_user_keys(self) -> None:
        test_user = SystemUserFactory(pk=562)
        other_user = SystemUserFactory()

        key = MTPRotoKeyFactory(
            user=test_user,
            vds=self.vds,
            is_active=True,
            was_deleted=False,
        )
        MTPRotoKeyFactory(
            user=other_user,
            vds=self.vds,
            is_active=True,
            was_deleted=False,
        )

        result = get_active_broadcast_keys(testing=True)
        self.assertEqual(list(result), [key])
