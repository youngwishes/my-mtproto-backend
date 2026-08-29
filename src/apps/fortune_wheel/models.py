from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseDjangoModel


class FortuneSpin(BaseDjangoModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fortune_spins",
        verbose_name="пользователь",
    )
    prize_apples = models.PositiveIntegerField("выиграно яблок")

    class Meta:
        verbose_name = "вращение колеса"
        verbose_name_plural = "вращения колеса"
        ordering = ("-created_at", "-pk")
        indexes = [
            models.Index(
                fields=("user", "-created_at"),
                name="fortune_user_created_idx",
            )
        ]
