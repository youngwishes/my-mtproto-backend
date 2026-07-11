from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, final

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from apps.users.exceptions import AlreadyUsedFree


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class DailyFreeTrialGrantService:
    """Ежедневно выдаёт бесплатный период не более чем десяти пользователям."""

    get_candidates: Callable[[], Iterable[Any]]
    activate_free_trial: Callable[..., Any]
    get_active_key: Callable[..., Any]
    get_active_servers: Callable[[], Iterable[Any]]
    send_message: Callable[..., None]
    admin_telegram_id: int

    def __call__(self) -> None:
        processed_count = 0
        activated_count = 0
        notified_count = 0

        for user in self.get_candidates():
            if activated_count >= 10:
                break
            processed_count += 1

            try:
                issued_key = self.activate_free_trial(
                    username=user.username,
                    notify_on_error=False,
                )
            except AlreadyUsedFree:
                continue
            except Exception:
                continue

            activated_count += 1
            try:
                key = self.get_active_key(user=user)
                servers = self.get_active_servers()
                markup = InlineKeyboardMarkup(
                    keyboard=[
                        [
                            InlineKeyboardButton(
                                text=server.location,
                                url=key.get_proxy_link(server_name=server.name),
                            )
                        ]
                        for server in servers
                    ]
                )
                self.send_message(
                    chat_id=int(user.username),
                    text=(
                        "🎁 <b>Для тебя открыт бесплатный доступ!</b>\n\n"
                        "Теперь Telegram может работать быстрее и стабильнее — "
                        f"доступ активен до <b>{issued_key.expired_date}</b>.\n\n"
                        "👇 <b>Выбери сервер и подключись прямо сейчас:</b>"
                    ),
                    markup=markup,
                )
                notified_count += 1
            except Exception:
                continue

        try:
            self.send_message(
                chat_id=int(self.admin_telegram_id),
                text=(
                    "Ежедневная выдача бесплатных периодов завершена.\n\n"
                    f"Перебрано кандидатов: {processed_count}\n"
                    f"Активировано периодов: {activated_count}\n"
                    f"Уведомлено пользователей: {notified_count}"
                ),
            )
        except Exception:
            pass


def get_daily_free_trial_grant_service() -> DailyFreeTrialGrantService:
    from django.conf import settings

    from apps.core.telegram.transport import send_telegram_message
    from apps.users.selectors import get_daily_free_trial_candidates
    from apps.users.services.first_free_link_service import get_first_free_link_service
    from apps.vds.selectors import get_active_key, get_all_active_vds_instances

    return DailyFreeTrialGrantService(
        get_candidates=get_daily_free_trial_candidates,
        activate_free_trial=get_first_free_link_service(),
        get_active_key=get_active_key,
        get_active_servers=get_all_active_vds_instances,
        send_message=send_telegram_message,
        admin_telegram_id=settings.MY_TELEGRAM_ID,
    )
