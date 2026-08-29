from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from unittest.mock import patch

from django.db import DatabaseError, close_old_connections
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from apps.fortune_wheel.constants import prize_for_ticket
from apps.fortune_wheel.exceptions import (
    FortuneWheelCooldown,
    FortuneWheelRegistrationRequired,
    FortuneWheelRetryable,
)
from apps.fortune_wheel.models import FortuneSpin
from apps.fortune_wheel.services import (
    GetFortuneWheelStatusService,
    SpinFortuneWheelService,
)
from apps.fortune_wheel.services.dtos import FortuneWheelSpinOut
from apps.users.tests.factories import SystemUserFactory


NOW = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)


class PrizeSelectionTest(SimpleTestCase):
    def test_ticket_boundaries_follow_fixed_prize_distribution(self) -> None:
        expected = {
            0: 5,
            19: 5,
            20: 10,
            49: 10,
            50: 15,
            74: 15,
            75: 25,
            94: 25,
            95: 60,
            98: 60,
            99: 100,
        }

        self.assertEqual(
            {ticket: prize_for_ticket(ticket=ticket) for ticket in expected},
            expected,
        )


class SpinFortuneWheelServiceTest(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory(
            username="1487189460",
            legal_terms_accepted=True,
            apple_balance=7,
        )

    def make_service(self, *, now: datetime = NOW, ticket: int = 20):
        return SpinFortuneWheelService(
            clock=lambda: now,
            ticket_source=lambda: ticket,
        )

    def test_first_spin_credits_prize_and_records_same_result_atomically(self) -> None:
        result = self.make_service()(
            telegram_id=self.user.username,
        )

        self.user.refresh_from_db()
        spin = FortuneSpin.objects.get(user=self.user)
        self.assertEqual(result.prize_apples, 10)
        self.assertEqual(result.spun_at, NOW)
        self.assertEqual(result.next_spin_at, NOW + timedelta(days=10))
        self.assertEqual(self.user.apple_balance, 17)
        self.assertEqual(spin.prize_apples, 10)
        self.assertEqual(spin.created_at, NOW)

    def test_spin_before_240_hours_preserves_balance_and_history(self) -> None:
        spin = FortuneSpin.objects.create(user=self.user, prize_apples=5)
        FortuneSpin.objects.filter(pk=spin.pk).update(
            created_at=NOW - timedelta(hours=239, minutes=59)
        )

        with self.assertRaises(FortuneWheelCooldown) as raised:
            self.make_service()(telegram_id=self.user.username)

        self.user.refresh_from_db()
        self.assertEqual(self.user.apple_balance, 7)
        self.assertEqual(FortuneSpin.objects.filter(user=self.user).count(), 1)
        self.assertEqual(raised.exception.context["last_prize"], 5)
        self.assertEqual(
            raised.exception.context["next_spin_at"],
            NOW + timedelta(minutes=1),
        )

    def test_spin_at_exactly_240_hours_is_allowed(self) -> None:
        spin = FortuneSpin.objects.create(user=self.user, prize_apples=5)
        FortuneSpin.objects.filter(pk=spin.pk).update(
            created_at=NOW - timedelta(hours=240)
        )

        result = self.make_service(ticket=99)(telegram_id=self.user.username)

        self.user.refresh_from_db()
        self.assertEqual(result.prize_apples, 100)
        self.assertEqual(self.user.apple_balance, 107)
        self.assertEqual(FortuneSpin.objects.filter(user=self.user).count(), 2)

    def test_user_without_accepted_terms_cannot_spin(self) -> None:
        self.user.legal_terms_accepted = False
        self.user.save(update_fields=["legal_terms_accepted"])

        with self.assertRaises(FortuneWheelRegistrationRequired):
            self.make_service()(telegram_id=self.user.username)

        self.assertFalse(FortuneSpin.objects.filter(user=self.user).exists())

    def test_database_failure_rolls_back_balance_and_spin(self) -> None:
        with patch(
            "apps.fortune_wheel.services.spin.create_fortune_spin",
            side_effect=DatabaseError,
        ):
            with self.assertRaises(FortuneWheelRetryable):
                self.make_service()(telegram_id=self.user.username)

        self.user.refresh_from_db()
        self.assertEqual(self.user.apple_balance, 7)
        self.assertFalse(FortuneSpin.objects.filter(user=self.user).exists())


class GetFortuneWheelStatusServiceTest(TestCase):
    def setUp(self) -> None:
        self.service = GetFortuneWheelStatusService(clock=lambda: NOW)

    def test_registered_user_without_history_can_spin_immediately(self) -> None:
        user = SystemUserFactory(
            username="first-spin",
            legal_terms_accepted=True,
        )

        result = self.service(telegram_id=user.username)

        self.assertTrue(result.registered)
        self.assertTrue(result.can_spin)
        self.assertIsNone(result.last_prize)
        self.assertIsNone(result.next_spin_at)

    def test_recent_spin_returns_last_prize_and_next_time(self) -> None:
        user = SystemUserFactory(
            username="waiting-user",
            legal_terms_accepted=True,
        )
        spin = FortuneSpin.objects.create(user=user, prize_apples=60)
        FortuneSpin.objects.filter(pk=spin.pk).update(
            created_at=NOW - timedelta(days=2)
        )

        result = self.service(telegram_id=user.username)

        self.assertTrue(result.registered)
        self.assertFalse(result.can_spin)
        self.assertEqual(result.last_prize, 60)
        self.assertEqual(result.next_spin_at, NOW + timedelta(days=8))

    def test_unknown_user_requires_registration(self) -> None:
        result = self.service(telegram_id="unknown")

        self.assertFalse(result.registered)
        self.assertFalse(result.can_spin)
        self.assertIsNone(result.last_prize)
        self.assertIsNone(result.next_spin_at)


class SpinFortuneWheelConcurrencyTest(TransactionTestCase):
    available_apps = ("apps.users", "apps.fortune_wheel")

    def test_concurrent_first_spin_has_one_credit_and_one_history_row(self) -> None:
        user = SystemUserFactory(
            username="concurrent-wheel-user",
            legal_terms_accepted=True,
        )
        barrier = Barrier(2)

        def spin() -> (
            FortuneWheelSpinOut | FortuneWheelRetryable | FortuneWheelCooldown
        ):
            close_old_connections()
            barrier.wait()
            try:
                return SpinFortuneWheelService(
                    clock=lambda: NOW,
                    ticket_source=lambda: 0,
                )(telegram_id=user.username)
            except (FortuneWheelRetryable, FortuneWheelCooldown) as exc:
                return exc
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: spin(), range(2)))

        user.refresh_from_db()
        self.assertEqual(
            sum(isinstance(item, FortuneWheelSpinOut) for item in outcomes),
            1,
        )
        self.assertEqual(
            sum(isinstance(item, FortuneWheelCooldown) for item in outcomes),
            1,
        )
        self.assertFalse(
            any(isinstance(item, FortuneWheelRetryable) for item in outcomes)
        )
        self.assertEqual(user.apple_balance, 5)
        self.assertEqual(FortuneSpin.objects.filter(user=user).count(), 1)
