from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Protocol, final

from django.db import OperationalError, transaction
from django.utils import timezone

from apps.payments.enums import (
    CryptoPaymentIntentStatusEnum,
    PaymentKindEnum,
    PaymentProviderEnum,
)
from apps.payments.exceptions import CryptoPaymentRetryable
from apps.payments.selectors import (
    claim_crypto_intent_for_fulfillment,
    conditionally_transition_crypto_intent,
    finalize_crypto_intent_fulfillment,
    get_crypto_intent_by_id,
    get_payment_by_identity,
)
from apps.payments.services.create_payment_service import get_create_payment_service
from apps.payments.services.dtos import (
    ApplyCryptoPaymentOut,
    CreateGiftCertificateIn,
    CreatePaymentIn,
)
from apps.payments.services.gift_certificates import (
    get_create_gift_certificate_service,
)
from apps.vds.exceptions import KeysLimitReached
from apps.vpn.services import get_fulfill_vpn_purchase_service
from apps.vpn.services.dtos import FulfillVPNPaymentIn

if TYPE_CHECKING:
    from apps.payments.services.create_payment_service import CreatePaymentService
    from apps.payments.services.dtos import ValidatedCryptoPaymentDTO
    from apps.payments.services.gift_certificates import CreateGiftCertificateService
    from apps.vpn.services import FulfillVPNPurchaseService


class EnqueueCryptoNotification(Protocol):
    def __call__(self, *, intent_id: int) -> None: ...


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ApplyCryptoPaymentService:
    """Атомарно применяет проверенный Crypto Pay платёж ровно один раз."""

    create_payment_service: CreatePaymentService
    fulfill_vpn_purchase_service: FulfillVPNPurchaseService
    create_gift_certificate_service: CreateGiftCertificateService
    enqueue_notification: EnqueueCryptoNotification
    clock: Callable[[], datetime]

    def __call__(
        self,
        *,
        payment: ValidatedCryptoPaymentDTO,
    ) -> ApplyCryptoPaymentOut:
        intent = get_crypto_intent_by_id(intent_id=payment.intent_id)
        if intent is None:
            raise CryptoPaymentRetryable("0", reason_code="intent_missing")

        try:
            with transaction.atomic():
                claimed = claim_crypto_intent_for_fulfillment(
                    intent_id=intent.pk,
                    attempted_at=self.clock(),
                )
                if claimed == 0:
                    current = get_crypto_intent_by_id(intent_id=intent.pk)
                    if (
                        current is not None
                        and current.status
                        == CryptoPaymentIntentStatusEnum.FULFILLED
                    ):
                        return ApplyCryptoPaymentOut(
                            fulfilled=False,
                            already_fulfilled=True,
                        )
                    raise CryptoPaymentRetryable(
                        intent.initiator.username,
                        reason_code="processing",
                    )

                charge_id = str(payment.invoice.invoice_id)
                if intent.purchase_kind == PaymentKindEnum.SUBSCRIPTION:
                    self.create_payment_service(
                        payment=CreatePaymentIn(
                            username=intent.initiator.username,
                            charge_id=charge_id,
                            provider=PaymentProviderEnum.CRYPTO_PAY,
                        ),
                        send_success_notification=False,
                    )
                elif intent.purchase_kind == PaymentKindEnum.VPN_SUBSCRIPTION:
                    self.fulfill_vpn_purchase_service(
                        payment=FulfillVPNPaymentIn(
                            username=intent.initiator.username,
                            charge_id=charge_id,
                            provider=PaymentProviderEnum.CRYPTO_PAY,
                            product_code=intent.product_code,
                        )
                    )
                else:
                    self.create_gift_certificate_service(
                        certificate=CreateGiftCertificateIn(
                            username=intent.initiator.username,
                            charge_id=charge_id,
                            provider=PaymentProviderEnum.CRYPTO_PAY,
                        )
                    )

                stored = get_payment_by_identity(
                    provider=PaymentProviderEnum.CRYPTO_PAY,
                    charge_id=charge_id,
                    kind=intent.purchase_kind,
                )
                if stored is None:
                    raise CryptoPaymentRetryable(
                        intent.initiator.username,
                        reason_code="payment_missing",
                    )
                if payment.invoice.paid_at is None:
                    raise CryptoPaymentRetryable(
                        intent.initiator.username,
                        reason_code="paid_at_missing",
                    )

                conditionally_transition_crypto_intent(
                    intent_id=intent.pk,
                    from_statuses=(CryptoPaymentIntentStatusEnum.PROCESSING,),
                    to_status=CryptoPaymentIntentStatusEnum.PROCESSING,
                    updates={"last_error_code": ""},
                )
                finalized = finalize_crypto_intent_fulfillment(
                    intent_id=intent.pk,
                    payment_id=stored.pk,
                    paid_at=payment.invoice.paid_at,
                    fulfilled_at=self.clock(),
                )
                if finalized != 1:
                    raise CryptoPaymentRetryable(
                        intent.initiator.username,
                        reason_code="finalize_conflict",
                    )

                transaction.on_commit(
                    lambda intent_id=intent.pk: self.enqueue_notification(
                        intent_id=intent_id,
                    )
                )
                return ApplyCryptoPaymentOut(
                    fulfilled=True,
                    already_fulfilled=False,
                )
        except (OperationalError, CryptoPaymentRetryable, KeysLimitReached) as exc:
            for _ in range(3):
                try:
                    conditionally_transition_crypto_intent(
                        intent_id=intent.pk,
                        from_statuses=(
                            CryptoPaymentIntentStatusEnum.ACTIVE,
                            CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
                            CryptoPaymentIntentStatusEnum.RETRYABLE,
                        ),
                        to_status=CryptoPaymentIntentStatusEnum.RETRYABLE,
                        updates={"last_error_code": "fulfillment_retryable"},
                    )
                    break
                except OperationalError:
                    time.sleep(0.05)
                    continue
            if isinstance(exc, KeysLimitReached):
                raise CryptoPaymentRetryable(
                    intent.initiator.username,
                    reason_code="fulfillment_retryable",
                ) from exc
            raise


def _enqueue_crypto_notification(*, intent_id: int) -> None:
    from apps.payments.tasks import notify_crypto_purchase_task

    notify_crypto_purchase_task.delay(intent_id)


def get_apply_crypto_payment_service() -> ApplyCryptoPaymentService:
    return ApplyCryptoPaymentService(
        create_payment_service=get_create_payment_service(),
        fulfill_vpn_purchase_service=get_fulfill_vpn_purchase_service(),
        create_gift_certificate_service=get_create_gift_certificate_service(),
        enqueue_notification=_enqueue_crypto_notification,
        clock=timezone.now,
    )
