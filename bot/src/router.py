from __future__ import annotations

from aiogram import Router

from domains.free_trial.handlers import router as free_trial_router
from domains.links.handlers import router as links_router
from domains.payments.handlers import router as payments_router
from domains.referrals.handlers import router as referrals_router

main_router = Router()
main_router.include_routers(
    free_trial_router,
    payments_router,
    referrals_router,
    links_router,
)
