from __future__ import annotations

from django.test import TestCase

from apps.users.selectors import (
    get_user_by_username,
    get_free_used_count,
    get_total_referrals_count,
    get_active_referrals_count,
)
from apps.users.tests.factories import SystemUserFactory


class TestGetUserByUsername(TestCase):
    def test_returns_user_when_exists(self) -> None:
        user = SystemUserFactory(username="123456")
        result = get_user_by_username(username="123456")
        self.assertEqual(result, user)

    def test_returns_none_when_not_found(self) -> None:
        result = get_user_by_username(username="nonexistent")
        self.assertIsNone(result)


class TestGetFreeUsedCount(TestCase):
    def test_returns_zero_when_no_users(self) -> None:
        self.assertEqual(get_free_used_count(), 0)

    def test_returns_count_of_users_with_free_used(self) -> None:
        SystemUserFactory(first_month_free_used=True)
        SystemUserFactory(first_month_free_used=True)
        SystemUserFactory(first_month_free_used=False)
        self.assertEqual(get_free_used_count(), 2)


class TestGetTotalReferralsCount(TestCase):
    def test_returns_zero_when_no_referrals(self) -> None:
        self.assertEqual(get_total_referrals_count(username="user1"), 0)

    def test_returns_count_of_invited_users(self) -> None:
        SystemUserFactory(invited_from_username="user1")
        SystemUserFactory(invited_from_username="user1")
        SystemUserFactory(invited_from_username="other")
        self.assertEqual(get_total_referrals_count(username="user1"), 2)


class TestGetActiveReferralsCount(TestCase):
    def test_returns_zero_when_no_active_referrals(self) -> None:
        SystemUserFactory(invited_from_username="user1", referral_activated=False)
        self.assertEqual(get_active_referrals_count(username="user1"), 0)

    def test_returns_count_of_active_referrals(self) -> None:
        SystemUserFactory(invited_from_username="user1", referral_activated=True)
        SystemUserFactory(invited_from_username="user1", referral_activated=True)
        SystemUserFactory(invited_from_username="user1", referral_activated=False)
        self.assertEqual(get_active_referrals_count(username="user1"), 2)
