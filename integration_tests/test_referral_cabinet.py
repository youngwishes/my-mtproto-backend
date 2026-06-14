"""Флоу 3: реферальный кабинет — ReferralsClient.get_cabinet.

→ POST /users/referral/cabinet/.
"""

from __future__ import annotations

from . import db, helpers


async def test_cabinet_counts_and_link(username):
    clients = helpers.make_clients()
    # arrange: 5 рефералов, из них 3 активированных
    await db.aw(db.create_user)(username)
    refs = await db.aw(db.create_referrals)(
        username, total=5, active=3, prefix=f"{username}r"
    )
    try:
        cabinet = await clients.referrals.get_cabinet(telegram_id=username)
        assert cabinet.total_referrals_count == 5
        assert cabinet.active_referrals_count == 3
        assert cabinet.link_activated_count == 0
        assert cabinet.referral_link and username in cabinet.referral_link
    finally:
        await db.aw(db.cleanup_users)(refs)
