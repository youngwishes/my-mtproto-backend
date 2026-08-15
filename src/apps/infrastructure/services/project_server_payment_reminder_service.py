from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from html import escape
from typing import TYPE_CHECKING, final

from django.conf import settings

from apps.core.telegram.transport import send_telegram_message
from apps.infrastructure.selectors import get_project_servers_due_by

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from datetime import date

    from apps.infrastructure.models import ProjectServer


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ProjectServerPaymentReminderService:
    get_due_servers: Callable[..., Iterable[ProjectServer]]
    send_message: Callable[..., None]
    admin_telegram_id: int
    telegram_timeout: int

    def __call__(self, *, today: date) -> None:
        servers = list(self.get_due_servers(through_date=today + timedelta(days=1)))
        if not servers:
            return

        blocks = [
            self._format_server(server=server, today=today) for server in servers
        ]
        text = "<b>Оплата проектных серверов</b>\n\n" + "\n\n".join(blocks)
        self.send_message(
            chat_id=self.admin_telegram_id,
            text=text,
            timeout=self.telegram_timeout,
        )

    @staticmethod
    def _format_server(*, server: ProjectServer, today: date) -> str:
        if server.next_payment_date == today + timedelta(days=1):
            status = "Завтра"
        elif server.next_payment_date == today:
            status = "Сегодня"
        else:
            days_overdue = (today - server.next_payment_date).days
            status = f"Просрочено ({days_overdue} дн.)"

        return "\n".join(
            (
                f"<b>Статус:</b> {escape(status)}",
                f"<b>IPv4:</b> {escape(str(server.ipv4))}",
                f"<b>Хостинг:</b> {escape(str(server.hosting.name))}",
                (
                    f"<b>Стоимость:</b> {escape(f'{server.price:.2f}')} "
                    f"{escape(str(server.currency))}"
                ),
                (
                    "<b>Дата оплаты:</b> "
                    f"{escape(server.next_payment_date.strftime('%d.%m.%Y'))}"
                ),
                f"<b>Назначение:</b> {escape(str(server.description))}",
            )
        )


def get_project_server_payment_reminder_service(
) -> ProjectServerPaymentReminderService:
    return ProjectServerPaymentReminderService(
        get_due_servers=get_project_servers_due_by,
        send_message=send_telegram_message,
        admin_telegram_id=int(settings.MY_TELEGRAM_ID),
        telegram_timeout=settings.TELEGRAM_TIMEOUT,
    )
