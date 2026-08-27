from __future__ import annotations

import pytest
from src.domains.payments import (
    AppleRedemptionPreview,
    AppleRedemptionResult,
    AppleStatus,
)
from src.exceptions import (
    APIError,
)

from tests.fakes import FakeCallback, make_deps
from tests.handler_support import (
    FakePayments,
)


async def test_apples_status_shows_progress_and_always_offers_spend_action():
    from src.handlers.apples import process_apples_status

    payments = FakePayments(
        apple_status=AppleStatus(
            balance=37,
            eligible_purchase_count=4,
            level="Садовник",
            rate_percent=10,
            next_level_purchase_count=7,
            purchases_to_next_level=3,
            is_max_level=False,
            redeemable_days=2,
            missing_apples=0,
            has_existing_key=True,
        )
    )
    callback = FakeCallback(user_id=42, data="apples_status")

    await process_apples_status(callback, make_deps(payments=payments))

    assert callback.answers == [((), {})]
    assert payments.apple_status_calls == [42]
    text, markup = callback.message.edits[0]
    assert text == (
        "🍏 <b>Мои яблоки</b>\n\n"
        "Баланс: <b>37 🍏</b>\n"
        "Покупок MTProxy: <b>4</b>\n"
        "Уровень: <b>Садовник</b>\n"
        "Кэшбэк: <b>10%</b>\n"
        "До следующего уровня: <b>3</b>\n\n"
        "Курс: <b>15 🍏 = 1 день</b>"
    )
    assert [
        [(button.text, button.callback_data) for button in row]
        for row in markup.inline_keyboard
    ] == [
        [("🍏 Потратить яблоки", "apples_spend")],
        [("🔙 Назад", "show_mtproxy_menu")],
    ]


async def test_apples_status_shows_max_level_without_progress_count():
    from src.handlers.apples import process_apples_status

    payments = FakePayments(
        apple_status=AppleStatus(
            balance=7,
            eligible_purchase_count=8,
            level="Мастер сада",
            rate_percent=15,
            next_level_purchase_count=None,
            purchases_to_next_level=None,
            is_max_level=True,
            redeemable_days=0,
            missing_apples=8,
            has_existing_key=False,
        )
    )
    callback = FakeCallback(user_id=42, data="apples_status")

    await process_apples_status(callback, make_deps(payments=payments))

    text, markup = callback.message.edits[0]
    assert "Максимальный уровень достигнут" in text
    assert "До следующего уровня" not in text
    assert markup.inline_keyboard[0][0].callback_data == "apples_spend"


async def test_apples_spend_offers_one_day_and_all_saved_backend_modes():
    from src.handlers.apples import process_apples_spend

    payments = FakePayments(
        apple_status=AppleStatus(
            balance=37,
            eligible_purchase_count=7,
            level="Мастер сада",
            rate_percent=15,
            next_level_purchase_count=None,
            purchases_to_next_level=None,
            is_max_level=True,
            redeemable_days=2,
            missing_apples=0,
            has_existing_key=True,
        )
    )
    callback = FakeCallback(user_id=42, data="apples_spend")

    await process_apples_spend(callback, make_deps(payments=payments))

    assert payments.apple_status_calls == [42]
    assert payments.apple_preview_calls == []
    text, markup = callback.message.edits[0]
    assert "Баланс: <b>37 🍏</b>" in text
    assert "Доступно дней: <b>2</b>" in text
    assert text.rstrip().endswith("Выбери вариант продления:")
    assert [
        [(button.text, button.callback_data) for button in row]
        for row in markup.inline_keyboard
    ] == [
        [("Обменять на 1 день — 15 🍏", "apples_redeem_one")],
        [("Обменять все яблоки", "apples_redeem_all")],
        [("🔙 Назад", "apples_status")],
    ]


async def test_apples_spend_below_rate_shows_exact_missing_count_without_preview():
    from src.handlers.apples import process_apples_spend

    payments = FakePayments(
        apple_status=AppleStatus(
            balance=7,
            eligible_purchase_count=0,
            level="Новичок",
            rate_percent=5,
            next_level_purchase_count=4,
            purchases_to_next_level=4,
            is_max_level=False,
            redeemable_days=0,
            missing_apples=8,
            has_existing_key=True,
        )
    )
    callback = FakeCallback(user_id=42, data="apples_spend")

    await process_apples_spend(callback, make_deps(payments=payments))

    text, markup = callback.message.edits[0]
    assert text == (
        "🍏 Для обмена не хватает <b>8 🍏</b>.\nКурс: <b>15 🍏 = 1 день</b>"
    )
    assert payments.apple_preview_calls == []
    assert [
        [button.callback_data for button in row] for row in markup.inline_keyboard
    ] == [["apples_status"]]


async def test_apples_spend_without_existing_key_stops_before_preview():
    from src.handlers.apples import process_apples_spend

    payments = FakePayments(
        apple_status=AppleStatus(
            balance=30,
            eligible_purchase_count=1,
            level="Новичок",
            rate_percent=5,
            next_level_purchase_count=4,
            purchases_to_next_level=3,
            is_max_level=False,
            redeemable_days=2,
            missing_apples=0,
            has_existing_key=False,
        )
    )
    callback = FakeCallback(user_id=42, data="apples_spend")

    await process_apples_spend(callback, make_deps(payments=payments))

    text, markup = callback.message.edits[0]
    assert text == (
        "🍏 Яблоки можно потратить только на продление "
        "своего существующего MTProxy-ключа."
    )
    assert payments.apple_preview_calls == []
    assert markup.inline_keyboard[0][0].callback_data == "apples_status"


@pytest.mark.parametrize(
    ("handler_name", "callback_data", "mode", "apples_spent", "days"),
    [
        ("process_apples_redeem_one", "apples_redeem_one", "one_day", 15, 1),
        ("process_apples_redeem_all", "apples_redeem_all", "all", 30, 2),
    ],
)
async def test_apples_preview_uses_only_saved_quote_and_requires_confirmation(
    handler_name: str,
    callback_data: str,
    mode: str,
    apples_spent: int,
    days: int,
):
    from src.handlers import apples as apples_module

    payments = FakePayments(
        apple_preview=AppleRedemptionPreview(
            confirmation_id=501,
            mode=mode,
            apples_spent=apples_spent,
            days=days,
            projected_expired_date="2026-08-21",
        )
    )
    callback = FakeCallback(user_id=42, data=callback_data)

    await getattr(apples_module, handler_name)(
        callback,
        make_deps(payments=payments),
    )

    assert payments.apple_preview_calls == [(42, mode)]
    assert payments.apple_confirm_calls == []
    text, markup = callback.message.edits[0]
    assert f"Списать: <b>{apples_spent} 🍏</b>" in text
    assert f"Добавить дней: <b>{days}</b>" in text
    assert "Продление до: <b>21.08.2026</b>" in text
    assert "Подтвердить обмен?" in text
    assert [
        [(button.text, button.callback_data) for button in row]
        for row in markup.inline_keyboard
    ] == [
        [("✅ Подтвердить", "apples_confirm:501")],
        [("🔙 Назад", "apples_spend")],
    ]


async def test_apples_confirm_renders_committed_37_to_30_two_days_and_7_balance():
    from src.handlers.apples import process_apples_confirm

    payments = FakePayments(
        apple_result=AppleRedemptionResult(
            apples_spent=30,
            days=2,
            expired_date="2026-08-22",
            balance=7,
        )
    )
    callback = FakeCallback(user_id=42, data="apples_confirm:501")

    await process_apples_confirm(callback, make_deps(payments=payments))

    assert payments.apple_confirm_calls == [(42, 501)]
    text, markup = callback.message.edits[0]
    assert text == (
        "✅ <b>Яблоки обменены</b>\n\n"
        "Списано: <b>30 🍏</b>\n"
        "Добавлено дней: <b>2</b>\n"
        "Продление до: <b>22.08.2026</b>\n"
        "Баланс: <b>7 🍏</b>"
    )
    assert [
        [button.callback_data for button in row] for row in markup.inline_keyboard
    ] == [
        ["apples_status"],
        ["show_mtproxy_menu"],
    ]


async def test_repeated_apples_confirmation_displays_same_committed_result():
    from src.handlers.apples import process_apples_confirm

    payments = FakePayments(
        apple_result=AppleRedemptionResult(
            apples_spent=15,
            days=1,
            expired_date="2026-08-21",
            balance=0,
        )
    )
    callbacks = [
        FakeCallback(user_id=42, data="apples_confirm:777"),
        FakeCallback(user_id=42, data="apples_confirm:777"),
    ]

    for callback in callbacks:
        await process_apples_confirm(callback, make_deps(payments=payments))

    assert payments.apple_confirm_calls == [(42, 777), (42, 777)]
    assert callbacks[0].message.edits[0][0] == callbacks[1].message.edits[0][0]
    assert "Продление до: <b>21.08.2026</b>" in (callbacks[1].message.edits[0][0])


async def test_apples_preview_and_stale_confirm_preserve_backend_safe_errors():
    from src.handlers.apples import (
        process_apples_confirm,
        process_apples_redeem_one,
    )

    no_key = APIError(
        42,
        message="Для обмена яблок нужен существующий MTProxy-ключ.",
    )
    preview_payments = FakePayments(apple_preview_error=no_key)
    preview_callback = FakeCallback(user_id=42, data="apples_redeem_one")

    with pytest.raises(APIError) as preview_exc:
        await process_apples_redeem_one(
            preview_callback,
            make_deps(payments=preview_payments),
        )

    assert preview_exc.value is no_key
    assert preview_callback.message.edits == []

    stale = APIError(
        42,
        message="Условия обмена изменились. Создайте новый предпросмотр.",
    )
    confirm_payments = FakePayments(apple_confirm_error=stale)
    confirm_callback = FakeCallback(user_id=42, data="apples_confirm:501")

    with pytest.raises(APIError) as confirm_exc:
        await process_apples_confirm(
            confirm_callback,
            make_deps(payments=confirm_payments),
        )

    assert confirm_exc.value is stale
    assert confirm_payments.apple_confirm_calls == [(42, 501)]
    assert confirm_callback.message.edits == []
