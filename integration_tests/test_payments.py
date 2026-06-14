"""Флоу 7: оплата — PaymentsClient → POST /payments/buy/, GET /payments/."""

from __future__ import annotations

import pytest

from src.exceptions import APIError

from . import db, helpers

PROVIDER = "yukassa"


async def test_buy_new_user_issues_key_and_payment(username):
    clients = helpers.make_clients()
    await db.aw(db.create_user)(username)  # юзер есть, ключа нет

    await clients.payments.confirm_purchase(
        telegram_id=username, charge_id="it-charge-new", provider=PROVIDER
    )

    key = await db.aw(db.get_active_key)(username)
    assert key is not None
    await helpers.assert_present_on_all_vds(username, present=True)
    assert await db.aw(db.count_payments)(username) == 1


async def test_buy_extends_existing_key_same_token(username):
    clients = helpers.make_clients()
    await clients.free_trial.claim(telegram_id=username)
    key1 = await db.aw(db.get_active_key)(username)
    token1, exp1 = key1.token, key1.expired_date

    await clients.payments.confirm_purchase(
        telegram_id=username, charge_id="it-charge-ext", provider=PROVIDER
    )

    key2 = await db.aw(db.get_active_key)(username)
    assert key2.token == token1          # ключ продлён, не пересоздан
    assert key2.expired_date > exp1      # срок увеличен
    assert await db.aw(db.count_payments)(username) == 1


async def test_buy_unknown_user_bad_payment_data(username):
    clients = helpers.make_clients()
    with pytest.raises(APIError) as ei:
        await clients.payments.confirm_purchase(
            telegram_id=username, charge_id="x", provider=PROVIDER
        )
    helpers.assert_status(ei.value, "400")


async def test_payment_history_survives_reissue_of_new_key(username):
    # Payment.key = SET_NULL: выдача нового ключа не сносит историю платежей.
    clients = helpers.make_clients()
    await db.aw(db.create_user)(username)
    await clients.payments.confirm_purchase(
        telegram_id=username, charge_id="it-charge-hist", provider=PROVIDER
    )
    assert await db.aw(db.count_payments)(username) == 1
    # повторная бесплатная выдача удалит старый ключ (IssueKeyService), но не платёж
    await db.aw(db.create_user)(username, first_month_free_used=False)
    await clients.free_trial.claim(telegram_id=username)
    assert await db.aw(db.count_payments)(username) == 1


async def test_get_card_and_stars_invoice(username):
    clients = helpers.make_clients()
    card = await clients.payments.get_card_invoice()
    assert card.title and card.prices
    stars = await clients.payments.get_stars_invoice()
    assert stars.title and stars.prices
