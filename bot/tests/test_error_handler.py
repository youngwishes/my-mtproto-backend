from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram.types import ErrorEvent, Update

from src import error_handler
from src.exceptions import APIError


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[object, str]] = []

    async def send_message(self, *, chat_id, text, **kwargs) -> None:
        self.sent.append((chat_id, text))


@pytest.fixture
def fake_bot(monkeypatch) -> FakeBot:
    bot = FakeBot()
    monkeypatch.setattr(error_handler, "bot", bot)
    monkeypatch.setattr(error_handler, "settings", SimpleNamespace(my_telegram_id="999"))
    return bot


def _event(exc: Exception) -> ErrorEvent:
    return ErrorEvent(update=Update(update_id=1), exception=exc)


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


async def test_skips_user_message_when_no_telegram_id(fake_bot: FakeBot):
    exc = APIError(telegram_id=None, request_url="http://backend/x", error="boom")

    handled = await error_handler.handle_service_errors(_event(exc))

    assert handled is True
    recipients = [chat_id for chat_id, _ in fake_bot.sent]
    assert recipients == ["999"]  # only the admin alert
