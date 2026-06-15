from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery

from src import keyboards
from src.messages import MY_SERVERS_TEXT, REISSUE_CONFIRM_TEXT, REISSUE_DONE_BANNER

if TYPE_CHECKING:
    from src.dependencies import Dependencies

router = Router()


async def _show_servers(
    callback: CallbackQuery, deps: Dependencies, *, banner: str = ""
) -> None:
    servers = await deps.links.get_my_servers(telegram_id=str(callback.message.chat.id))
    await callback.message.edit_text(
        text=banner + MY_SERVERS_TEXT.format(expired_date=servers.expired_date),
        reply_markup=keyboards.my_servers(servers.servers),
    )


@router.callback_query(F.data == "my_servers")
async def process_my_servers(callback: CallbackQuery, deps: Dependencies):
    await callback.answer()
    await _show_servers(callback, deps)


@router.callback_query(F.data == "update_link")
async def update_link(callback: CallbackQuery, deps: Dependencies):
    """Tap on «Перевыпустить» — show the confirmation screen, reissue nothing yet."""
    await callback.answer()
    await callback.message.edit_text(
        text=REISSUE_CONFIRM_TEXT,
        reply_markup=keyboards.confirm_reissue(),
    )


@router.callback_query(F.data == "update_link_confirm")
async def update_link_confirm(callback: CallbackQuery, deps: Dependencies):
    """User confirmed — reissue and land on «Мои серверы» with a success banner."""
    await callback.answer()
    await deps.links.reissue(telegram_id=str(callback.message.chat.id))
    await _show_servers(callback, deps, banner=REISSUE_DONE_BANNER)
