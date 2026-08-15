from __future__ import annotations

from django.db import models


class ProjectServerCurrency(models.TextChoices):
    USDT = "USDT", "USDT"
    RUB = "RUB", "RUB"
    EUR = "EUR", "EUR"
    USD = "USD", "USD"
