from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from apps.core.decorators import log_service_error
from apps.core.telegram.transport import send_telegram_message
from apps.notifications.resolvers import resolve_context
from apps.notifications.selectors import get_users_by_filter

if TYPE_CHECKING:
    from apps.notifications.models import Mailing


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class SendMailingService:
    """Выполняет рассылку по фильтру пользователей с отслеживанием результатов."""

    mailing: Mailing

    @log_service_error
    def __call__(self) -> None:
        mailing = self.mailing
        mailing.mark_as_sending()

        users = get_users_by_filter(
            filter_type=mailing.filter_type,
            params=mailing.filter_params,
        )
        template = mailing.template

        sent_count = 0
        failed_count = 0

        for user in users.iterator():
            personal_context = resolve_context(
                resolver_type=mailing.context_resolver,
                user=user,
            )
            if personal_context is None:
                continue
            merged_context = {**mailing.context, **personal_context}
            message = template.render(context=merged_context)
            try:
                send_telegram_message(
                    chat_id=int(user.username),
                    text=message.text,
                    markup=message.markup,
                )
                sent_count += 1
            except Exception:
                failed_count += 1
            time.sleep(0.05)

        mailing.sent_count = sent_count
        mailing.failed_count = failed_count
        mailing.save(update_fields=["sent_count", "failed_count"])

        if sent_count == 0 and failed_count > 0:
            mailing.mark_as_failed()
        elif failed_count > 0:
            mailing.mark_as_partially_completed()
        else:
            mailing.mark_as_completed()
