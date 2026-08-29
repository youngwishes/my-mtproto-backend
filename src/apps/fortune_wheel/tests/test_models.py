from __future__ import annotations

from django.db import models
from django.test import TestCase

from apps.core.models import BaseDjangoModel
from apps.fortune_wheel.models import FortuneSpin
from apps.users.tests.factories import SystemUserFactory


class FortuneSpinModelTest(TestCase):
    def test_spin_is_an_immutable_user_prize_ledger_entry(self) -> None:
        user = SystemUserFactory()

        spin = FortuneSpin.objects.create(user=user, prize_apples=25)

        self.assertIsInstance(spin, BaseDjangoModel)
        self.assertEqual(spin.user, user)
        self.assertEqual(spin.prize_apples, 25)
        self.assertIsNotNone(spin.created_at)
        self.assertEqual(
            FortuneSpin._meta.get_field("user").remote_field.on_delete,
            models.PROTECT,
        )
