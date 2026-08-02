from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, final

from django.db import OperationalError

from apps.payments.exceptions import CryptoPaymentRetryable
from apps.payments.selectors import (
    get_unfinished_crypto_intents,
    get_unnotified_fulfilled_crypto_intents,
    mark_crypto_intent_provider_expired,
)
from apps.payments.services.dtos import CryptoWebhookWarningDTO

if TYPE_CHECKING:
    from apps.payments.clients import CryptoPayClient
    from apps.payments.services.apply_crypto_payment import ApplyCryptoPaymentService
    from apps.payments.services.validate_crypto_invoice import (
        ValidateCryptoInvoiceService,
    )


logger = logging.getLogger(__name__)
GET_INVOICES_BATCH_SIZE = 100
NOTIFICATION_BATCH_SIZE = 100


class EnqueueCryptoNotification(Protocol):
    def __call__(self, *, intent_id: int) -> None: ...


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReconcileCryptoPaymentsService:
    """Reconcile bounded unfinished Crypto Pay intents with the provider."""

    crypto_pay_client: CryptoPayClient
    validate_invoice_service: ValidateCryptoInvoiceService
    apply_payment_service: ApplyCryptoPaymentService
    enqueue_notification: EnqueueCryptoNotification

    def __call__(self) -> dict[str, int]:
        counters = {
            "checked": 0,
            "paid": 0,
            "fulfilled": 0,
            "provider_expired": 0,
            "retryable_failed": 0,
            "notifications_enqueued": 0,
        }
        intents = list(get_unfinished_crypto_intents(limit=GET_INVOICES_BATCH_SIZE))
        notified_intent_ids: set[int] = set()

        for offset in range(0, len(intents), GET_INVOICES_BATCH_SIZE):
            batch = intents[offset : offset + GET_INVOICES_BATCH_SIZE]
            intents_by_invoice_id = {
                intent.provider_invoice_id: intent for intent in batch
            }
            invoices = self.crypto_pay_client.get_invoices(
                invoice_ids=[intent.provider_invoice_id for intent in batch],
            )
            for invoice in invoices:
                counters["checked"] += 1
                intent = intents_by_invoice_id[invoice.invoice_id]
                try:
                    if invoice.status == "paid":
                        counters["paid"] += 1
                        validated = self.validate_invoice_service(
                            update_id=None,
                            invoice=invoice,
                        )
                        if isinstance(validated, CryptoWebhookWarningDTO):
                            counters["retryable_failed"] += 1
                            self._log_invoice_failure(
                                invoice_id=invoice.invoice_id,
                                intent_id=intent.pk,
                                reason_code=validated.reason,
                            )
                            continue
                        applied = self.apply_payment_service(payment=validated)
                        counters["fulfilled"] += int(applied.fulfilled)
                        if applied.fulfilled:
                            notified_intent_ids.add(intent.pk)
                    elif invoice.status == "expired":
                        counters["provider_expired"] += (
                            mark_crypto_intent_provider_expired(intent_id=intent.pk)
                        )
                except (CryptoPaymentRetryable, OperationalError) as exc:
                    counters["retryable_failed"] += 1
                    self._log_invoice_failure(
                        invoice_id=invoice.invoice_id,
                        intent_id=intent.pk,
                        reason_code=self._reason_code(exc=exc),
                    )

        for intent in get_unnotified_fulfilled_crypto_intents(
            limit=NOTIFICATION_BATCH_SIZE,
        ):
            if intent.pk in notified_intent_ids:
                continue
            self.enqueue_notification(intent_id=intent.pk)
            notified_intent_ids.add(intent.pk)
            counters["notifications_enqueued"] += 1
        return counters

    @staticmethod
    def _reason_code(*, exc: CryptoPaymentRetryable | OperationalError) -> str:
        if isinstance(exc, CryptoPaymentRetryable):
            return str(exc.context.get("reason_code", "retryable"))
        return "operational_error"

    @staticmethod
    def _log_invoice_failure(
        *, invoice_id: int, intent_id: int, reason_code: str
    ) -> None:
        logger.warning(
            "crypto_reconciliation_invoice_failed",
            extra={
                "invoice_id": invoice_id,
                "intent_id": intent_id,
                "reason_code": reason_code,
            },
        )


def _enqueue_crypto_notification(*, intent_id: int) -> None:
    from apps.payments.tasks import notify_crypto_purchase_task

    notify_crypto_purchase_task.delay(intent_id)


def get_reconcile_crypto_payments_service() -> ReconcileCryptoPaymentsService:
    from apps.payments.clients import get_crypto_pay_client
    from apps.payments.services.apply_crypto_payment import (
        get_apply_crypto_payment_service,
    )
    from apps.payments.services.validate_crypto_invoice import (
        get_validate_crypto_invoice_service,
    )

    return ReconcileCryptoPaymentsService(
        crypto_pay_client=get_crypto_pay_client(),
        validate_invoice_service=get_validate_crypto_invoice_service(),
        apply_payment_service=get_apply_crypto_payment_service(),
        enqueue_notification=_enqueue_crypto_notification,
    )
