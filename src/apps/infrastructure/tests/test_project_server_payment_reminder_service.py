from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.infrastructure.models import ProjectServer
from apps.infrastructure.tests.factories import ProjectServerFactory
from apps.vds.models import Hosting


class _SingleUseIterable:
    def __init__(self, values: list[ProjectServer]) -> None:
        self._values = values
        self.iterations = 0

    def __iter__(self) -> Iterator[ProjectServer]:
        self.iterations += 1
        if self.iterations > 1:
            raise AssertionError("due servers were materialized more than once")
        return iter(self._values)


class TestProjectServerPaymentReminderService(TestCase):
    def test_empty_due_set_sends_nothing_and_queries_through_tomorrow(self) -> None:
        from apps.infrastructure.services import ProjectServerPaymentReminderService

        requested_dates: list[date] = []
        sent_messages: list[dict[str, object]] = []

        def get_due_servers(*, through_date: date) -> list[ProjectServer]:
            requested_dates.append(through_date)
            return []

        def send_message(**kwargs: object) -> None:
            sent_messages.append(kwargs)

        service = ProjectServerPaymentReminderService(
            get_due_servers=get_due_servers,
            send_message=send_message,
            admin_telegram_id=123,
            telegram_timeout=5,
        )

        service(today=date(2026, 8, 15))

        self.assertEqual(requested_dates, [date(2026, 8, 16)])
        self.assertEqual(sent_messages, [])

    def test_sends_one_html_safe_summary_with_all_statuses_and_fields(self) -> None:
        from apps.infrastructure.services import ProjectServerPaymentReminderService

        today = date(2026, 8, 15)
        hosting = Hosting(
            name="Host <primary> & partner",
            link="https://example.com",
        )
        servers = [
            ProjectServer(
                ipv4="192.0.2.1",
                hosting=hosting,
                price=Decimal("9.5"),
                currency="USD",
                next_payment_date=today - timedelta(days=2),
                description="API <prod> & monitoring",
            ),
            ProjectServer(
                ipv4="192.0.2.2",
                hosting=hosting,
                price=Decimal("10"),
                currency="EUR",
                next_payment_date=today,
                description="database",
            ),
            ProjectServer(
                ipv4="192.0.2.3",
                hosting=hosting,
                price=Decimal("11.25"),
                currency="USDT",
                next_payment_date=today + timedelta(days=1),
                description="proxy",
            ),
        ]
        due_servers = _SingleUseIterable(servers)
        sent_messages: list[dict[str, object]] = []
        service = ProjectServerPaymentReminderService(
            get_due_servers=lambda **_: due_servers,
            send_message=lambda **kwargs: sent_messages.append(kwargs),
            admin_telegram_id=456,
            telegram_timeout=17,
        )

        service(today=today)

        self.assertEqual(due_servers.iterations, 1)
        self.assertEqual(
            sent_messages,
            [
                {
                    "chat_id": 456,
                    "timeout": 17,
                    "text": (
                        "<b>Оплата проектных серверов</b>\n\n"
                        "<b>Статус:</b> Просрочено (2 дн.)\n"
                        "<b>IPv4:</b> 192.0.2.1\n"
                        "<b>Хостинг:</b> Host &lt;primary&gt; &amp; partner\n"
                        "<b>Стоимость:</b> 9.50 USD\n"
                        "<b>Дата оплаты:</b> 13.08.2026\n"
                        "<b>Назначение:</b> API &lt;prod&gt; &amp; monitoring\n\n"
                        "<b>Статус:</b> Сегодня\n"
                        "<b>IPv4:</b> 192.0.2.2\n"
                        "<b>Хостинг:</b> Host &lt;primary&gt; &amp; partner\n"
                        "<b>Стоимость:</b> 10.00 EUR\n"
                        "<b>Дата оплаты:</b> 15.08.2026\n"
                        "<b>Назначение:</b> database\n\n"
                        "<b>Статус:</b> Завтра\n"
                        "<b>IPv4:</b> 192.0.2.3\n"
                        "<b>Хостинг:</b> Host &lt;primary&gt; &amp; partner\n"
                        "<b>Стоимость:</b> 11.25 USDT\n"
                        "<b>Дата оплаты:</b> 16.08.2026\n"
                        "<b>Назначение:</b> proxy"
                    ),
                }
            ],
        )

    def test_reminder_does_not_mutate_inventory(self) -> None:
        from apps.infrastructure.services import ProjectServerPaymentReminderService

        today = date(2026, 8, 15)
        server = ProjectServerFactory(
            is_active=True,
            next_payment_date=today - timedelta(days=1),
        )
        original_updated_at = server.updated_at
        service = ProjectServerPaymentReminderService(
            get_due_servers=lambda **_: [server],
            send_message=lambda **_: None,
            admin_telegram_id=123,
            telegram_timeout=5,
        )

        service(today=today)

        server.refresh_from_db()
        self.assertTrue(server.is_active)
        self.assertEqual(server.next_payment_date, today - timedelta(days=1))
        self.assertEqual(server.updated_at, original_updated_at)

    @override_settings(MY_TELEGRAM_ID="789", TELEGRAM_TIMEOUT=23)
    def test_factory_wires_selector_recipient_sender_and_timeout(self) -> None:
        from apps.infrastructure.services.project_server_payment_reminder_service import (
            get_project_server_payment_reminder_service,
        )

        today = date(2026, 8, 15)
        server = ProjectServer(
            ipv4="192.0.2.4",
            hosting=Hosting(name="Hosting", link="https://example.com"),
            price=Decimal("12"),
            currency="RUB",
            next_payment_date=today,
            description="worker",
        )
        with (
            patch(
                "apps.infrastructure.services.project_server_payment_reminder_service."
                "get_project_servers_due_by",
                return_value=[server],
            ) as selector,
            patch(
                "apps.infrastructure.services.project_server_payment_reminder_service."
                "send_telegram_message"
            ) as sender,
        ):
            get_project_server_payment_reminder_service()(today=today)

        selector.assert_called_once_with(through_date=date(2026, 8, 16))
        sender.assert_called_once()
        self.assertEqual(sender.call_args.kwargs["chat_id"], 789)
        self.assertEqual(sender.call_args.kwargs["timeout"], 23)
        self.assertIn("192.0.2.4", sender.call_args.kwargs["text"])
