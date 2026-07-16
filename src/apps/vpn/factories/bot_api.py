from __future__ import annotations

from apps.payments.services import (
    AcceptPaymentReceiptService,
    ApprovePaymentIntentService,
    CreatePaymentIntentService,
    get_accept_payment_receipt_service,
    get_approve_payment_intent_service,
    get_create_payment_intent_service,
)
from apps.vpn.services import (
    get_check_vpn_sale_availability_service,
    get_reissue_vpn_access_by_username_service,
    get_vpn_access_status_service,
)


def _schedule_receipt(*, receipt_id: int) -> None:
    from apps.vpn.tasks.payment_receipts import apply_payment_receipt_task

    apply_payment_receipt_task.delay(receipt_id=receipt_id)


def get_create_vpn_payment_intent_service() -> CreatePaymentIntentService:
    return get_create_payment_intent_service(
        check_sale_availability=get_check_vpn_sale_availability_service(),
    )


def get_approve_vpn_payment_intent_service() -> ApprovePaymentIntentService:
    return get_approve_payment_intent_service(
        check_sale_availability=get_check_vpn_sale_availability_service(),
    )


def get_accept_vpn_payment_receipt_service() -> AcceptPaymentReceiptService:
    return get_accept_payment_receipt_service(schedule_receipt=_schedule_receipt)


__all__ = [
    "get_accept_vpn_payment_receipt_service",
    "get_approve_vpn_payment_intent_service",
    "get_create_vpn_payment_intent_service",
    "get_reissue_vpn_access_by_username_service",
    "get_vpn_access_status_service",
]
