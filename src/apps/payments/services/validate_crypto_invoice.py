from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from apps.payments.selectors.crypto import (
    get_crypto_intent_by_provider_invoice_id,
)
from apps.payments.services.dtos import (
    CryptoWebhookWarningDTO,
    ValidatedCryptoPaymentDTO,
)

if TYPE_CHECKING:
    from apps.payments.services.dtos import CryptoInvoiceDTO


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ValidateCryptoInvoiceService:
    """Validate stored invoice semantics without exposing webhook secrets or PII."""

    def __call__(
        self,
        *,
        update_id: int | None,
        invoice: CryptoInvoiceDTO,
    ) -> ValidatedCryptoPaymentDTO | CryptoWebhookWarningDTO:
        intent = get_crypto_intent_by_provider_invoice_id(
            provider_invoice_id=invoice.invoice_id,
        )
        if intent is None:
            return CryptoWebhookWarningDTO(
                reason="unknown_invoice",
                update_id=update_id,
                invoice_id=invoice.invoice_id,
                intent_id=None,
            )

        checks = (
            (invoice.status == "paid", "status_mismatch"),
            (invoice.payload == str(intent.public_id), "payload_mismatch"),
            (
                invoice.currency_type == "fiat" and invoice.fiat == "RUB",
                "fiat_mismatch",
            ),
            (invoice.amount == intent.rub_amount, "amount_mismatch"),
            (
                invoice.accepted_assets == frozenset({"USDT", "TON"}),
                "accepted_assets_mismatch",
            ),
            (invoice.paid_asset in {"USDT", "TON"}, "paid_asset_mismatch"),
            (
                invoice.expiration_date == intent.provider_expires_at,
                "expiration_mismatch",
            ),
            (
                invoice.paid_at is not None
                and invoice.paid_at <= intent.provider_expires_at,
                "paid_at_mismatch",
            ),
        )
        for matches, reason in checks:
            if not matches:
                return CryptoWebhookWarningDTO(
                    reason=reason,
                    update_id=update_id,
                    invoice_id=invoice.invoice_id,
                    intent_id=intent.pk,
                )

        return ValidatedCryptoPaymentDTO(intent_id=intent.pk, invoice=invoice)


def get_validate_crypto_invoice_service() -> ValidateCryptoInvoiceService:
    return ValidateCryptoInvoiceService()
