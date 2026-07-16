from aiogram import Router

from src.handlers import free_trial, links, payments, referrals, start, vpn

router = Router()
router.include_routers(
    start.router,
    free_trial.router,
    links.router,
    referrals.router,
    vpn.router,
    payments.router,
)

__all__ = ["router"]
