from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from apps.payments.apple_cashback import (
    APPLES_PER_DAY,
    AppleLevelDTO,
    build_apple_purchase_identity_key,
    calculate_apples,
    get_apple_level,
)


class TestAppleCashbackRules(SimpleTestCase):
    def test_purchase_count_boundaries_return_the_fixed_level_and_next_target(self) -> None:
        cases = (
            (0, AppleLevelDTO(name="Новичок", rate_percent=5, next_level_purchase_count=4)),
            (3, AppleLevelDTO(name="Новичок", rate_percent=5, next_level_purchase_count=4)),
            (4, AppleLevelDTO(name="Садовник", rate_percent=10, next_level_purchase_count=7)),
            (6, AppleLevelDTO(name="Садовник", rate_percent=10, next_level_purchase_count=7)),
            (7, AppleLevelDTO(name="Мастер сада", rate_percent=15, next_level_purchase_count=None)),
        )

        for eligible_purchase_count, expected in cases:
            with self.subTest(eligible_purchase_count=eligible_purchase_count):
                self.assertEqual(
                    get_apple_level(
                        eligible_purchase_count=eligible_purchase_count,
                    ),
                    expected,
                )

    def test_cashback_uses_half_up_rounding_at_each_level(self) -> None:
        cases = (
            (Decimal("99.00"), 5, 5),
            (Decimal("99.00"), 10, 10),
            (Decimal("99.00"), 15, 15),
            (Decimal("10.00"), 5, 1),
            (Decimal("10.00"), 15, 2),
        )

        for nominal_rub_amount, rate_percent, expected in cases:
            with self.subTest(
                nominal_rub_amount=nominal_rub_amount,
                rate_percent=rate_percent,
            ):
                self.assertEqual(
                    calculate_apples(
                        nominal_rub_amount=nominal_rub_amount,
                        rate_percent=rate_percent,
                    ),
                    expected,
                )

    def test_identity_key_preserves_provider_charge_and_kind(self) -> None:
        self.assertEqual(
            build_apple_purchase_identity_key(
                provider="stars",
                charge_id="provider:charge",
                kind="subscription",
            ),
            "stars:provider:charge:subscription",
        )

    def test_redemption_rate_is_fifteen_apples_per_day(self) -> None:
        self.assertEqual(APPLES_PER_DAY, 15)
