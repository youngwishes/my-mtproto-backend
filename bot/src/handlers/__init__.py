from aiogram import Router

from src.handlers import free_trial, links, payments, referrals, start

router = Router()
router.include_routers(
    start.router,
    free_trial.router,
    links.router,
    referrals.router,
    payments.router,
)

__all__ = ["router"]
