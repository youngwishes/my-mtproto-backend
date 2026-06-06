from __future__ import annotations

from dataclasses import dataclass
from typing import final

from apps.core.service import log_service_error
from apps.core.telegram.transport import send
from apps.notifications.selectors import get_template


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class SendNotificationService:
    slug: str
    context: dict

    @log_service_error
    def __call__(self, *, chat_id: int) -> None:
        template = get_template(slug=self.slug)
        message = template.render(context=self.context)
        send(chat_id=chat_id, text=message.text, markup=message.markup)
