from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, final

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.decorators import log_service_error
from apps.payments.apple_cashback import (
    build_apple_purchase_identity_key,
    calculate_apples,
    get_apple_level,
)
from apps.payments.enums import PaymentKindEnum, ProductCodeEnum
from apps.payments.exceptions import BadPaymentData
from apps.payments.selectors import (
    count_apple_cashback_purchases,
    create_apple_cashback_purchase,
    create_subscription_payment,
    get_active_product_by_code,
    get_apple_cashback_purchase_by_identity,
    get_payment_user_for_update,
)
from apps.payments.services.extend_key_service import (
    ExtendKeyService,
    get_extend_key_service,
)
from apps.vds.selectors import get_active_key
from apps.vds.services import get_issue_key_on_commit_service

if TYPE_CHECKING:
    from apps.payments.models import AppleCashbackPurchase
    from apps.payments.services.dtos import (
        ApplePurchaseOutcomeDTO,
        CreatePaymentIn,
        CreatePaymentResult,
    )
    from apps.vds.services import IssueKeyService


def _saved_loyalty_outcome(
    *, purchase: AppleCashbackPurchase
) -> ApplePurchaseOutcomeDTO:
    from apps.payments.services.dtos import ApplePurchaseOutcomeDTO

    assert purchase.rate_percent is not None
    resulting_level = get_apple_level(
        eligible_purchase_count=purchase.eligible_purchase_count_after
    )
    previous_level = get_apple_level(
        eligible_purchase_count=purchase.eligible_purchase_count_after - 1
    )
    return ApplePurchaseOutcomeDTO(
        apples_earned=purchase.apples_earned,
        rate_percent=purchase.rate_percent,
        balance=purchase.balance_after,
        eligible_purchase_count=purchase.eligible_purchase_count_after,
        level=resulting_level.name,
        level_up=resulting_level.name != previous_level.name,
        next_purchase_rate_percent=resulting_level.rate_percent,
    )


def _saved_subscription_result(
    *, purchase: AppleCashbackPurchase, username: str
) -> CreatePaymentResult:
    from apps.payments.services.dtos import (
        CreatePaymentOut,
        HistoricalPurchaseReplayDTO,
    )

    if purchase.payment.user.username != username:
        raise BadPaymentData(telegram_id=username)
    if purchase.rate_percent is None:
        return HistoricalPurchaseReplayDTO()
    if purchase.result_expired_at is None:
        raise BadPaymentData(telegram_id=username)
    return CreatePaymentOut(
        expired_date=purchase.result_expired_at.date().strftime("%d.%m.%y"),
        loyalty=_saved_loyalty_outcome(purchase=purchase),
    )


def _nominal_rub_amount(*, payment: CreatePaymentIn) -> Decimal:
    if payment.nominal_rub_amount is not None:
        amount = Decimal(payment.nominal_rub_amount)
        if amount <= 0:
            raise BadPaymentData(telegram_id=payment.username)
        return amount

    product = get_active_product_by_code(code=ProductCodeEnum.MTPROTO_30D)
    if product is None or product.currency != "RUB":
        raise BadPaymentData(telegram_id=payment.username)
    kopecks = Decimal(product.price)
    if kopecks <= 0 or kopecks != kopecks.to_integral_value():
        raise BadPaymentData(telegram_id=payment.username)
    return (kopecks / Decimal("100")).quantize(Decimal("0.01"))


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CreatePaymentService:
    """Fulfil one MTProxy payment and save its loyalty outcome atomically."""

    extend_key_service: ExtendKeyService
    issue_key_service: IssueKeyService

    @log_service_error
    def __call__(
        self,
        *,
        payment: CreatePaymentIn,
    ) -> CreatePaymentResult:
        if not payment.charge_id.strip():
            raise BadPaymentData(telegram_id=payment.username)
        identity_key = build_apple_purchase_identity_key(
            provider=payment.provider,
            charge_id=payment.charge_id,
            kind=PaymentKindEnum.SUBSCRIPTION,
        )

        try:
            with transaction.atomic():
                user = get_payment_user_for_update(username=payment.username)
                if user is None:
                    raise BadPaymentData(telegram_id=payment.username)
                existing = get_apple_cashback_purchase_by_identity(
                    identity_key=identity_key
                )
                if existing is not None:
                    return _saved_subscription_result(
                        purchase=existing,
                        username=payment.username,
                    )

                nominal_rub_amount = _nominal_rub_amount(payment=payment)
                eligible_purchase_count = count_apple_cashback_purchases(
                    user_id=user.pk
                )
                rate_percent = get_apple_level(
                    eligible_purchase_count=eligible_purchase_count
                ).rate_percent

                active_key = get_active_key(user=user)
                if active_key:
                    self.extend_key_service(
                        key=active_key,
                        reset_user_notified=True,
                    )
                    key = active_key
                else:
                    key = self.issue_key_service(
                        user=user,
                        expired_date=timezone.now()
                        + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
                    )

                saved_payment = create_subscription_payment(
                    user_id=user.pk,
                    key_id=key.pk,
                    charge_id=payment.charge_id,
                    provider=payment.provider,
                )
                apples_earned = calculate_apples(
                    nominal_rub_amount=nominal_rub_amount,
                    rate_percent=rate_percent,
                )
                balance_after = user.apple_balance + apples_earned
                purchase = create_apple_cashback_purchase(
                    payment_id=saved_payment.pk,
                    identity_key=identity_key,
                    rate_percent=rate_percent,
                    apples_earned=apples_earned,
                    balance_after=balance_after,
                    eligible_purchase_count_after=eligible_purchase_count + 1,
                    result_expired_at=key.expired_date,
                )
                user.apple_balance = balance_after
                user.save(update_fields=["apple_balance"])
                return _saved_subscription_result(
                    purchase=purchase,
                    username=payment.username,
                )
        except IntegrityError:
            winner = get_apple_cashback_purchase_by_identity(identity_key=identity_key)
            if winner is None:
                raise
            return _saved_subscription_result(
                purchase=winner,
                username=payment.username,
            )


def get_create_payment_service() -> CreatePaymentService:
    return CreatePaymentService(
        extend_key_service=get_extend_key_service(),
        issue_key_service=get_issue_key_on_commit_service(),
    )
