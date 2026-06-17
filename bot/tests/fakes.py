"""Lightweight fakes for handler tests.

aiogram's ``Message``/``CallbackQuery`` are heavy pydantic models; handlers only
touch a handful of attributes, so we fake exactly those and record outgoing
calls for assertions.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.dependencies import Dependencies


class FakeMessage:
    def __init__(
        self,
        *,
        chat_id: int = 42,
        user_id: int = 42,
        username: str | None = "bob",
        text: str = "/start",
    ) -> None:
        self.chat = SimpleNamespace(id=chat_id)
        self.from_user = SimpleNamespace(id=user_id, username=username)
        self.text = text
        self.answers: list[tuple] = []
        self.edits: list[tuple] = []

    async def answer(self, text=None, *, reply_markup=None, **kwargs) -> None:
        self.answers.append((text, reply_markup))

    async def edit_text(self, text=None, *, reply_markup=None, **kwargs) -> None:
        self.edits.append((text, reply_markup))


class FakeCallback:
    def __init__(
        self, *, chat_id: int = 42, user_id: int = 42, username: str | None = "bob"
    ) -> None:
        # Сообщение с inline-кнопкой отправлено ботом, поэтому его from_user —
        # это бот, а не нажавший пользователь (как в реальном aiogram).
        self.message = FakeMessage(chat_id=chat_id, user_id=user_id, username="thebot")
        # from_user коллбэка — тот, кто нажал кнопку.
        self.from_user = SimpleNamespace(id=user_id, username=username)
        self.answers: list[tuple] = []

    async def answer(self, *args, **kwargs) -> None:
        self.answers.append((args, kwargs))


class FakeBot:
    def __init__(self) -> None:
        self.invoices: list[dict] = []
        self.pre_checkout: list[tuple] = []

    async def send_invoice(self, **kwargs) -> None:
        self.invoices.append(kwargs)

    async def answer_pre_checkout_query(self, *args, **kwargs) -> None:
        self.pre_checkout.append((args, kwargs))


def make_deps(**overrides) -> Dependencies:
    base = dict(free_trial=None, links=None, referrals=None, payments=None)
    base.update(overrides)
    return Dependencies(**base)
