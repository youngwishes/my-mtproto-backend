from __future__ import annotations

from datetime import date

from django.db.models import QuerySet

from apps.infrastructure.models import ProjectServer


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
