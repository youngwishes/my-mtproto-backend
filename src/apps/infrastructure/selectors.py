from __future__ import annotations

from typing import TYPE_CHECKING

from apps.infrastructure.models import ProjectServer

if TYPE_CHECKING:
    from datetime import date

    from django.db.models import QuerySet


def get_project_servers_due_by(
    *,
    through_date: date,
) -> QuerySet[ProjectServer]:
    return (
        ProjectServer.objects.active()
        .filter(next_payment_date__lte=through_date)
        .select_related("hosting")
        .order_by("next_payment_date", "ipv4")
    )
