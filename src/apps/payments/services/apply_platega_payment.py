from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Protocol, final

from django.db import OperationalError, transaction
from django.utils import timezone

from apps.payments.enums import (
    PaymentKindEnum,
    PaymentProviderEnum,
    PlategaPaymentIntentStatusEnum,
)
from apps.payments.exceptions import PlategaPaymentRetryable
from apps.payments.selectors import (
    claim_platega_intent_for_fulfillment,
    claim_platega_notification_enqueue,
    clear_platega_notification_enqueue,
    finalize_platega_intent_fulfillment,
    get_payment_by_identity,
    get_platega_intent_by_id,
    mark_platega_intent_retryable,
)
from apps.payments.services.create_payment_service import (
    get_create_payment_service,
)
from apps.payments.services.dtos import (
    ApplyPlategaPaymentOut,
    CreateGiftCertificateIn,
    CreatePaymentIn,
)
from apps.payments.services.gift_certificates import (
    get_create_gift_certificate_service,
)
from apps.vpn.services import get_fulfill_vpn_purchase_service
from apps.vpn.services.dtos import FulfillVPNPaymentIn

if TYPE_CHECKING:
    from apps.payments.services.create_payment_service import CreatePaymentService
    from apps.payments.services.dtos import ValidatedPlategaPaymentDTO
    from apps.payments.services.gift_certificates import CreateGiftCertificateService
    from apps.vpn.services import FulfillVPNPurchaseService


class EnqueuePlategaNotification(Protocol):
    def __call__(self, *, intent_id: int) -> None: ...


def _mark_retryable(*, intent_id: int) -> None:
    for attempt in range(3):
        try:
            mark_platega_intent_retryable(
                intent_id=intent_id,
                error_code="fulfillment_retryable",
            )
            return
        except OperationalError:
            if attempt == 2:
                return
            time.sleep(0.05)


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ApplyPlategaPaymentService:
    """Atomically fulfil one validated Platega payment and claim enqueue."""

    create_payment_service: CreatePaymentService
    fulfill_vpn_purchase_service: FulfillVPNPurchaseService
    create_gift_certificate_service: CreateGiftCertificateService
    enqueue_notification: EnqueuePlategaNotification
    clock: Callable[[], datetime]

    def __call__(
        self,
        *,
        payment: ValidatedPlategaPaymentDTO,
    ) -> ApplyPlategaPaymentOut:
        initial_storage_failed = False
        try:
            intent = get_platega_intent_by_id(intent_id=payment.intent_id)
        except OperationalError:
            intent = None
            initial_storage_failed = True

        if (
            initial_storage_failed
            or intent is None
            or intent.provider_transaction_id != payment.transaction_id
        ):
            raise PlategaPaymentRetryable(
                "0",
                reason_code="fulfillment_retryable",
            )

        claimed = False
        retryable_failure = False
        try:
            with transaction.atomic():
                claimed_rows = claim_platega_intent_for_fulfillment(
                    intent_id=intent.pk,
                    attempted_at=self.clock(),
                )
                if claimed_rows == 0:
                    current = get_platega_intent_by_id(intent_id=intent.pk)
                    if (
                        current is not None
                        and current.status
                        == PlategaPaymentIntentStatusEnum.FULFILLED
                    ):
                        if current.notification_queued_at is None:
                            queued_at = self.clock()
                            queue_claimed = claim_platega_notification_enqueue(
                                intent_id=current.pk,
                                queued_at=queued_at,
                            )
                            if queue_claimed == 1:
                                self._enqueue_on_commit(
                                    intent_id=current.pk,
                                    queued_at=queued_at,
                                )
                        return ApplyPlategaPaymentOut(
                            fulfilled=False,
                            already_fulfilled=True,
                        )
                    raise PlategaPaymentRetryable(
                        "0",
                        reason_code="processing",
                    )
                claimed = True

                charge_id = str(payment.transaction_id)
                if intent.purchase_kind == PaymentKindEnum.SUBSCRIPTION:
                    self.create_payment_service(
                        payment=CreatePaymentIn(
                            username=intent.initiator.username,
                            charge_id=charge_id,
                            provider=PaymentProviderEnum.PLATEGA,
                        ),
                        send_success_notification=False,
                        notify_on_error=False,
                    )
                elif intent.purchase_kind == PaymentKindEnum.VPN_SUBSCRIPTION:
                    self.fulfill_vpn_purchase_service(
                        payment=FulfillVPNPaymentIn(
                            username=intent.initiator.username,
                            charge_id=charge_id,
                            provider=PaymentProviderEnum.PLATEGA,
                            product_code=intent.product_code,
                        ),
                        notify_on_error=False,
                    )
                elif intent.purchase_kind == PaymentKindEnum.GIFT_CERTIFICATE:
                    self.create_gift_certificate_service(
                        certificate=CreateGiftCertificateIn(
                            username=intent.initiator.username,
                            charge_id=charge_id,
                            provider=PaymentProviderEnum.PLATEGA,
                        ),
                        notify_on_error=False,
                    )
                else:
                    raise PlategaPaymentRetryable(
                        "0",
                        reason_code="fulfillment_retryable",
                    )

                stored = get_payment_by_identity(
                    provider=PaymentProviderEnum.PLATEGA,
                    charge_id=charge_id,
                    kind=intent.purchase_kind,
                )
                if stored is None:
                    raise PlategaPaymentRetryable(
                        "0",
                        reason_code="fulfillment_retryable",
                    )

                fulfilled_at = self.clock()
                finalized = finalize_platega_intent_fulfillment(
                    intent_id=intent.pk,
                    payment_id=stored.pk,
                    fulfilled_at=fulfilled_at,
                )
                if finalized != 1:
                    raise PlategaPaymentRetryable(
                        "0",
                        reason_code="fulfillment_retryable",
                    )

                queued_at = self.clock()
                if (
                    claim_platega_notification_enqueue(
                        intent_id=intent.pk,
                        queued_at=queued_at,
                    )
                    != 1
                ):
                    raise PlategaPaymentRetryable(
                        "0",
                        reason_code="fulfillment_retryable",
                    )
                self._enqueue_on_commit(
                    intent_id=intent.pk,
                    queued_at=queued_at,
                )
                return ApplyPlategaPaymentOut(
                    fulfilled=True,
                    already_fulfilled=False,
                )
        except PlategaPaymentRetryable as exc:
            if claimed:
                _mark_retryable(intent_id=intent.pk)
            if exc.context.get("reason_code") == "processing":
                raise
            retryable_failure = True
        except Exception:
            if claimed:
                _mark_retryable(intent_id=intent.pk)

            retryable_failure = True

        if retryable_failure:
            raise PlategaPaymentRetryable(
                "0",
                reason_code="fulfillment_retryable",
            )
        raise AssertionError("unreachable")

    def _enqueue_on_commit(self, *, intent_id: int, queued_at: datetime) -> None:
        def publish() -> None:
            publish_failed = False
            try:
                self.enqueue_notification(intent_id=intent_id)
            except Exception:
                clear_platega_notification_enqueue(
                    intent_id=intent_id,
                    queued_at=queued_at,
                )
                publish_failed = True

            if publish_failed:
                raise PlategaPaymentRetryable(
                    "0",
                    reason_code="fulfillment_retryable",
                )

        transaction.on_commit(publish)


def _enqueue_platega_notification(*, intent_id: int) -> None:
    from apps.payments.tasks import notify_platega_purchase_task

    notify_platega_purchase_task.delay(intent_id)


def get_apply_platega_payment_service() -> ApplyPlategaPaymentService:
    return ApplyPlategaPaymentService(
        create_payment_service=get_create_payment_service(),
        fulfill_vpn_purchase_service=get_fulfill_vpn_purchase_service(),
        create_gift_certificate_service=get_create_gift_certificate_service(),
        enqueue_notification=_enqueue_platega_notification,
        clock=timezone.now,
    )
