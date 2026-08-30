from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram.types import CallbackQuery, ErrorEvent, Update, User
from src.exceptions import APIError

from src import error_handler


class FakeDismissMessage:
    def __init__(self) -> None:
        self.deleted = False

    async def delete(self) -> None:
        self.deleted = True


class FakeDismissCallback:
    def __init__(self) -> None:
        self.message = FakeDismissMessage()
        self.answered = False

    async def answer(self) -> None:
        self.answered = True


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[object, str]] = []
        self.reply_markups: list[object | None] = []

    async def send_message(self, *, chat_id, text, **kwargs) -> None:
        self.sent.append((chat_id, text))
        self.reply_markups.append(kwargs.get("reply_markup"))


@pytest.fixture
def fake_bot(monkeypatch) -> FakeBot:
    bot = FakeBot()
    monkeypatch.setattr(error_handler, "bot", bot)
    monkeypatch.setattr(error_handler, "settings", SimpleNamespace(my_telegram_id="999"))
    return bot


def _event(exc: Exception, *, callback_data: str | None = None) -> ErrorEvent:
    callback_query = None
    if callback_data is not None:
        callback_query = CallbackQuery(
            id="callback-id",
            from_user=User(id=42, is_bot=False, first_name="User"),
            chat_instance="chat-instance",
            data=callback_data,
        )
    return ErrorEvent(
        update=Update(update_id=1, callback_query=callback_query),
        exception=exc,
    )


async def test_returns_false_and_stays_silent_for_non_service_error(fake_bot: FakeBot):
    handled = await error_handler.handle_service_errors(_event(ValueError("boom")))

    assert handled is False
    assert fake_bot.sent == []


async def test_notifies_user_and_admin_for_service_error(fake_bot: FakeBot):
    exc = APIError(telegram_id="42", request_url="http://backend/x", error="boom")

    handled = await error_handler.handle_service_errors(_event(exc))

    assert handled is True
    recipients = [chat_id for chat_id, _ in fake_bot.sent]
    assert "42" in recipients  # user gets the human-facing message
    assert "999" in recipients  # admin gets the system alert
    user_text = dict(fake_bot.sent)["42"]
    assert user_text == APIError.__doc__


async def test_notifies_only_user_for_backend_client_error(fake_bot: FakeBot):
    exc = APIError(
        telegram_id="42",
        request_url="http://backend/x",
        status_code=400,
        error="bad request",
        message="Проверьте введённые данные",
    )

    handled = await error_handler.handle_service_errors(_event(exc))

    assert handled is True
    assert fake_bot.sent == [("42", "Проверьте введённые данные")]
    assert fake_bot.reply_markups == [None]


@pytest.mark.parametrize(
    "callback_data",
    ["update_link_confirm", "vpn_reissue_confirm"],
)
async def test_reissue_error_has_dismiss_button(
    fake_bot: FakeBot,
    callback_data: str,
):
    exc = APIError(
        telegram_id="42",
        request_url="http://backend/api/v1/users/update-link/",
        status_code=400,
        error="bad request",
        message="🔒 Пожалуйста, подождите 5 минут с последнего обновления.",
    )

    handled = await error_handler.handle_service_errors(
        _event(exc, callback_data=callback_data)
    )

    assert handled is True
    markup = fake_bot.reply_markups[0]
    button = markup.inline_keyboard[0][0]
    assert button.text == "🧹 Понятно"
    assert button.callback_data == "dismiss_error_notification"


async def test_dismiss_error_notification_deletes_its_message():
    callback = FakeDismissCallback()

    await error_handler.dismiss_error_notification(callback)

    assert callback.answered is True
    assert callback.message.deleted is True


async def test_notifies_user_and_admin_for_backend_server_error(fake_bot: FakeBot):
    exc = APIError(
        telegram_id="42",
        request_url="http://backend/x",
        status_code=500,
        error="server error",
    )

    handled = await error_handler.handle_service_errors(_event(exc))

    assert handled is True
    recipients = [chat_id for chat_id, _ in fake_bot.sent]
    assert recipients == ["42", "999"]


async def test_skips_user_message_when_no_telegram_id(fake_bot: FakeBot):
    exc = APIError(telegram_id=None, request_url="http://backend/x", error="boom")

    handled = await error_handler.handle_service_errors(_event(exc))

    assert handled is True
    recipients = [chat_id for chat_id, _ in fake_bot.sent]
    assert recipients == ["999"]  # only the admin alert
