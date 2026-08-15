from __future__ import annotations

from datetime import date, timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.infrastructure.tests.factories import ProjectServerFactory


class TestGetProjectServersDueBy(TestCase):
    def test_returns_active_due_servers_in_date_ip_order(self) -> None:
        from apps.infrastructure.selectors import get_project_servers_due_by

        through_date = date(2026, 8, 16)
        later_ip = ProjectServerFactory(
            ipv4="192.0.2.20",
            next_payment_date=through_date,
        )
        overdue = ProjectServerFactory(
            ipv4="192.0.2.30",
            next_payment_date=through_date - timedelta(days=1),
        )
        earlier_ip = ProjectServerFactory(
            ipv4="192.0.2.10",
            next_payment_date=through_date,
        )
        ProjectServerFactory(
            next_payment_date=through_date + timedelta(days=1),
        )
        ProjectServerFactory(
            next_payment_date=through_date,
            is_active=False,
        )

        result = list(get_project_servers_due_by(through_date=through_date))

        self.assertEqual(result, [overdue, earlier_ip, later_ip])

    def test_preloads_hosting_without_additional_queries(self) -> None:
        from apps.infrastructure.selectors import get_project_servers_due_by

        through_date = date(2026, 8, 16)
        ProjectServerFactory(next_payment_date=through_date)

        servers = list(get_project_servers_due_by(through_date=through_date))

        with self.assertNumQueries(0):
            self.assertTrue(servers[0].hosting.name)

    def test_selection_performs_only_a_read(self) -> None:
        from apps.infrastructure.models import ProjectServer
        from apps.infrastructure.selectors import get_project_servers_due_by

        through_date = date(2026, 8, 16)
        server = ProjectServerFactory(next_payment_date=through_date)
        original_updated_at = server.updated_at

        with CaptureQueriesContext(connection) as queries:
            list(get_project_servers_due_by(through_date=through_date))

        self.assertTrue(queries.captured_queries)
        self.assertTrue(
            all(
                query["sql"].lstrip().upper().startswith("SELECT")
                for query in queries.captured_queries
            )
        )
        server.refresh_from_db()
        self.assertEqual(ProjectServer.objects.count(), 1)
        self.assertEqual(server.updated_at, original_updated_at)
