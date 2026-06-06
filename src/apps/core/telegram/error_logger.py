from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING

from django.conf import settings

from apps.core.telegram.transport import send_telegram_message

if TYPE_CHECKING:
    from apps.core.exceptions import BaseInfraError, BaseServiceError


def _log_error(
    exc: BaseInfraError | BaseServiceError,
    *,
    emoji: str,
    error_type: str,
    attention_text: str,
) -> None:
    error_dict = exc.to_dict()
    pretty_error = json.dumps(error_dict, indent=2, ensure_ascii=False)
    escaped_error = html.escape(pretty_error)
    send_telegram_message(
        chat_id=settings.MY_TELEGRAM_ID,
        text=(
            f"{emoji} <b>(BACKEND) Системное оповещение</b>\n\n"
            f"🛡 <b>Тип ошибки:</b> {error_type}\n"
            f"📋 <b>Детали:</b>\n"
            f"<code>{escaped_error}</code>\n\n"
            f"⚙️ <i>{attention_text}</i>"
        ),
        timeout=settings.TELEGRAM_TIMEOUT,
    )


def log_infra_error(exc: BaseInfraError) -> None:
    _log_error(
        exc,
        emoji="🔴",
        error_type="SERVER INTERNAL ERROR (500)",
        attention_text="Требуется СРОЧНОЕ внимание команды",
    )


def log_service_error(exc: BaseServiceError) -> None:
    _log_error(
        exc,
        emoji="🟡",
        error_type="SERVICE (400)",
        attention_text="Возможно, требуется внимание команды",
    )
