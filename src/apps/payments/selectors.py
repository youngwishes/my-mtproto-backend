from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Q, QuerySet, When

from apps.payments.enums import (
    CryptoPaymentIntentStatusEnum,
    PaymentKindEnum,
    PaymentMethodCodeEnum,
    PaymentProviderEnum,
    PlategaPaymentIntentStatusEnum,
)
from apps.payments.models import (
    AppleCashbackPurchase,
    AppleRedemption,
    CryptoPaymentIntent,
    GiftCertificate,
    Payment,
    PaymentMethod,
    PlategaPaymentIntent,
    Product,
)
from apps.users.models import SystemUser
from apps.vds.models import MTPRotoKey

if TYPE_CHECKING:
    from apps.payments.services.dtos.crypto_pay_dtos import CryptoInvoiceDTO
    from apps.payments.services.dtos.platega_dtos import PlategaTransactionDTO


_SUPPORTED_PAYMENT_METHOD_CODES = (
    PaymentMethodCodeEnum.PLATEGA_SBP,
    PaymentMethodCodeEnum.STARS,
    PaymentMethodCodeEnum.CRYPTO_PAY,
)


def get_active_payment_method_codes() -> tuple[str, ...]:
    order = Case(
        When(code=PaymentMethodCodeEnum.PLATEGA_SBP, then=0),
        When(code=PaymentMethodCodeEnum.STARS, then=1),
        When(code=PaymentMethodCodeEnum.CRYPTO_PAY, then=2),
        output_field=IntegerField(),
    )
    return tuple(
        PaymentMethod.objects.active()
        .filter(code__in=_SUPPORTED_PAYMENT_METHOD_CODES)
        .order_by(order)
        .values_list("code", flat=True)
    )


def get_active_priority_payment_method_codes() -> tuple[str, ...]:
    order = Case(
        When(code=PaymentMethodCodeEnum.PLATEGA_SBP, then=0),
        When(code=PaymentMethodCodeEnum.STARS, then=1),
        When(code=PaymentMethodCodeEnum.CRYPTO_PAY, then=2),
        output_field=IntegerField(),
    )
    return tuple(
        PaymentMethod.objects.active()
        .filter(is_priority=True, code__in=_SUPPORTED_PAYMENT_METHOD_CODES)
        .order_by(order)
        .values_list("code", flat=True)
    )


def get_payment_method_commission_percent(*, code: str) -> Decimal | None:
    return (
        PaymentMethod.objects.filter(code=code)
        .values_list("commission_percent", flat=True)
        .first()
    )


def get_active_product_by_code(*, code: str) -> Product | None:
    return Product.objects.active().filter(code=code).first()


def get_payment_user_for_update(*, username: str) -> SystemUser | None:
    """Return the payment owner while locking their mutable loyalty state."""
    return SystemUser.objects.select_for_update().filter(username=username).first()


def get_apple_cashback_purchase_by_identity(
    *, identity_key: str
) -> AppleCashbackPurchase | None:
    """Return the saved eligible-purchase outcome for a provider identity."""
    return (
        AppleCashbackPurchase.objects.select_related("payment", "payment__user")
        .filter(identity_key=identity_key)
        .first()
    )


def count_apple_cashback_purchases(*, user_id: int) -> int:
    """Count completed eligible purchases, including launch history."""
    return AppleCashbackPurchase.objects.filter(payment__user_id=user_id).count()


def get_existing_apple_redemption_key(
    *, user_id: int, now: datetime
) -> MTPRotoKey | None:
    """Select the user's best valid key, then their best existing dated key."""
    return _select_existing_apple_redemption_key(
        keys=MTPRotoKey.objects.filter(user_id=user_id),
        now=now,
    )


def get_existing_apple_redemption_key_for_update(
    *, user_id: int, now: datetime
) -> MTPRotoKey | None:
    """Lock and select the user's key eligible for confirmed redemption."""
    return _select_existing_apple_redemption_key(
        keys=MTPRotoKey.objects.select_for_update().filter(user_id=user_id),
        now=now,
    )


def _select_existing_apple_redemption_key(
    *, keys: QuerySet[MTPRotoKey], now: datetime
) -> MTPRotoKey | None:
    active = (
        keys.active()
        .filter(was_deleted=False, expired_date__gt=now)
        .order_by("-expired_date", "-pk")
        .first()
    )
    if active is not None:
        return active
    return keys.filter(expired_date__isnull=False).order_by(
        "-expired_date", "-pk"
    ).first()


def get_apple_redemption_for_update(
    *, confirmation_id: int
) -> AppleRedemption | None:
    """Lock a saved quote/outcome and load its owner."""
    return (
        AppleRedemption.objects.select_for_update()
        .select_related("user")
        .filter(pk=confirmation_id)
        .first()
    )


def create_apple_redemption(
    *,
    user_id: int,
    key_id: int,
    apples_spent: int,
    quoted_expired_at: datetime,
) -> AppleRedemption:
    """Persist one immutable pending apple-redemption quote."""
    return AppleRedemption.objects.create(
        user_id=user_id,
        key_id=key_id,
        apples_spent=apples_spent,
        quoted_expired_at=quoted_expired_at,
    )


def create_apple_cashback_purchase(
    *,
    payment_id: int,
    identity_key: str,
    rate_percent: int,
    apples_earned: int,
    balance_after: int,
    eligible_purchase_count_after: int,
    result_expired_at: datetime | None,
) -> AppleCashbackPurchase:
    """Persist the immutable loyalty snapshot for one eligible payment."""
    return AppleCashbackPurchase.objects.create(
        payment_id=payment_id,
        identity_key=identity_key,
        rate_percent=rate_percent,
        apples_earned=apples_earned,
        balance_after=balance_after,
        eligible_purchase_count_after=eligible_purchase_count_after,
        result_expired_at=result_expired_at,
    )


def get_vpn_payment_by_identity_for_update(
    *,
    provider: str,
    charge_id: str,
) -> Payment | None:
    """VPN-платёж с блокировкой строки для идемпотентной обработки."""
    return (
        Payment.objects.select_for_update()
        .filter(
            provider=provider,
            charge_id=charge_id,
            kind=PaymentKindEnum.VPN_SUBSCRIPTION,
        )
        .first()
    )


def get_vpn_payment_by_identity(*, provider: str, charge_id: str) -> Payment | None:
    """VPN-платёж по identity провайдера."""
    return Payment.objects.filter(
        provider=provider,
        charge_id=charge_id,
        kind=PaymentKindEnum.VPN_SUBSCRIPTION,
    ).first()


def create_vpn_payment(
    *,
    user_id: int,
    provider: str,
    charge_id: str,
) -> Payment:
    """Сохраняет успешный платёж VPN без связи с MTProto-ключом."""
    return Payment.objects.create(
        user_id=user_id,
        key=None,
        provider=provider,
        charge_id=charge_id,
        kind=PaymentKindEnum.VPN_SUBSCRIPTION,
    )


def normalize_gift_certificate_code(*, code: str) -> str:
    return code.strip().upper()


def get_gift_certificate_by_code(*, code: str) -> GiftCertificate | None:
    return GiftCertificate.objects.filter(
        code=normalize_gift_certificate_code(code=code),
    ).select_related("buyer", "payment", "activated_by").first()


def get_gift_certificate_by_payment_identity(
    *,
    provider: str,
    charge_id: str,
) -> GiftCertificate | None:
    return GiftCertificate.objects.filter(
        payment__kind=PaymentKindEnum.GIFT_CERTIFICATE,
        payment__provider=provider,
        payment__charge_id=charge_id,
    ).select_related("buyer", "payment", "activated_by").first()


def create_gift_certificate_payment(
    *, user_id: int, provider: str, charge_id: str
) -> Payment:
    """Persist one successful gift-certificate payment."""
    return Payment.objects.create(
        user_id=user_id,
        key=None,
        charge_id=charge_id,
        provider=provider,
        kind=PaymentKindEnum.GIFT_CERTIFICATE,
    )


def create_gift_certificate(
    *, code: str, buyer_id: int, payment_id: int, expires_at: datetime
) -> GiftCertificate:
    """Persist the gift result owned by its paying buyer."""
    return GiftCertificate.objects.create(
        code=code,
        buyer_id=buyer_id,
        payment_id=payment_id,
        expires_at=expires_at,
    )


def get_reusable_crypto_intent(
    *, initiator_id: int, purchase_kind: str, now: datetime
) -> CryptoPaymentIntent | None:
    return CryptoPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=CryptoPaymentIntentStatusEnum.ACTIVE,
        provider_expires_at__gt=now,
    ).first()


def get_creating_crypto_intent(
    *, initiator_id: int, purchase_kind: str
) -> CryptoPaymentIntent | None:
    return CryptoPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=CryptoPaymentIntentStatusEnum.CREATING,
    ).first()


def create_crypto_intent(
    *,
    initiator_id: int,
    purchase_kind: str,
    product_code: str,
    rub_amount: Decimal,
    public_id: UUID,
) -> CryptoPaymentIntent:
    return CryptoPaymentIntent.objects.create(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        product_code=product_code,
        rub_amount=rub_amount,
        public_id=public_id,
    )


def get_crypto_intent_by_provider_invoice_id(
    *, provider_invoice_id: int
) -> CryptoPaymentIntent | None:
    return CryptoPaymentIntent.objects.select_related("initiator", "payment").filter(
        provider_invoice_id=provider_invoice_id
    ).first()


def get_crypto_intent_by_id(*, intent_id: int) -> CryptoPaymentIntent | None:
    return CryptoPaymentIntent.objects.select_related("initiator", "payment").filter(
        pk=intent_id
    ).first()


def get_crypto_intent_for_notification(
    *, intent_id: int
) -> CryptoPaymentIntent | None:
    return (
        CryptoPaymentIntent.objects.select_related(
            "initiator",
            "payment",
            "payment__key",
            "payment__gift_certificate",
            "payment__apple_cashback_purchase",
            "payment__user__vpn_subscription",
        )
        .filter(
            pk=intent_id,
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            notification_sent_at__isnull=True,
        )
        .first()
    )


def get_unfinished_crypto_intents(*, limit: int) -> QuerySet[CryptoPaymentIntent]:
    return CryptoPaymentIntent.objects.select_related("initiator").filter(
        payment__isnull=True,
        status__in=(
            CryptoPaymentIntentStatusEnum.ACTIVE,
            CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
            CryptoPaymentIntentStatusEnum.RETRYABLE,
        ),
    ).order_by("pk")[:limit]


def get_unnotified_fulfilled_crypto_intents(
    *, limit: int
) -> QuerySet[CryptoPaymentIntent]:
    return (
        CryptoPaymentIntent.objects.select_related(
            "initiator",
            "payment",
            "payment__apple_cashback_purchase",
        )
        .filter(
            Q(purchase_kind=PaymentKindEnum.VPN_SUBSCRIPTION)
            | Q(payment__apple_cashback_purchase__rate_percent__isnull=False),
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            notification_sent_at__isnull=True,
        )
        .order_by("pk")[:limit]
    )


def get_payment_by_identity(
    *, provider: str, charge_id: str, kind: str
) -> Payment | None:
    return Payment.objects.filter(
        provider=provider,
        charge_id=charge_id,
        kind=kind,
    ).first()


def create_subscription_payment(
    *, user_id: int, key_id: int, charge_id: str, provider: str
) -> Payment:
    return Payment.objects.create(
        user_id=user_id,
        key_id=key_id,
        charge_id=charge_id,
        provider=provider,
        kind=PaymentKindEnum.SUBSCRIPTION,
    )


def conditionally_transition_crypto_intent(
    *,
    intent_id: int,
    from_statuses: tuple[str, ...],
    to_status: str,
    updates: dict[str, object],
) -> int:
    return CryptoPaymentIntent.objects.filter(
        pk=intent_id,
        status__in=from_statuses,
    ).update(status=to_status, **updates)


def claim_crypto_intent_for_fulfillment(
    *, intent_id: int, attempted_at: datetime
) -> int:
    return CryptoPaymentIntent.objects.filter(
        pk=intent_id,
        payment__isnull=True,
        status__in=(
            CryptoPaymentIntentStatusEnum.ACTIVE,
            CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
            CryptoPaymentIntentStatusEnum.RETRYABLE,
        ),
    ).update(
        status=CryptoPaymentIntentStatusEnum.PROCESSING,
        fulfillment_attempted_at=attempted_at,
        updated_at=attempted_at,
    )


def finalize_crypto_intent_fulfillment(
    *, intent_id: int, payment_id: int, paid_at: datetime, fulfilled_at: datetime
) -> int:
    return CryptoPaymentIntent.objects.filter(
        pk=intent_id,
        payment__isnull=True,
        status=CryptoPaymentIntentStatusEnum.PROCESSING,
    ).update(
        payment_id=payment_id,
        paid_at=paid_at,
        fulfilled_at=fulfilled_at,
        status=CryptoPaymentIntentStatusEnum.FULFILLED,
        updated_at=fulfilled_at,
    )


def mark_crypto_intent_retryable(*, intent_id: int, error_code: str) -> int:
    return CryptoPaymentIntent.objects.filter(
        pk=intent_id,
        payment__isnull=True,
        status=CryptoPaymentIntentStatusEnum.PROCESSING,
    ).update(
        status=CryptoPaymentIntentStatusEnum.RETRYABLE,
        last_error_code=error_code,
    )


def mark_crypto_notification_sent(*, intent_id: int, sent_at: datetime) -> int:
    return CryptoPaymentIntent.objects.filter(
        pk=intent_id,
        status=CryptoPaymentIntentStatusEnum.FULFILLED,
        notification_sent_at__isnull=True,
    ).update(notification_sent_at=sent_at, updated_at=sent_at)


def mark_crypto_intent_provider_expired(*, intent_id: int) -> int:
    return CryptoPaymentIntent.objects.filter(
        pk=intent_id,
        status__in=(
            CryptoPaymentIntentStatusEnum.ACTIVE,
            CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
        ),
    ).update(status=CryptoPaymentIntentStatusEnum.PROVIDER_EXPIRED)


def expire_active_crypto_intent(
    *, initiator_id: int, purchase_kind: str, now: datetime
) -> int:
    return CryptoPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=CryptoPaymentIntentStatusEnum.ACTIVE,
        provider_expires_at__lte=now,
    ).update(status=CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED, updated_at=now)


def fail_stale_creating_crypto_intent(
    *, initiator_id: int, purchase_kind: str, stale_before: datetime
) -> int:
    return CryptoPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=CryptoPaymentIntentStatusEnum.CREATING,
        created_at__lte=stale_before,
    ).update(
        status=CryptoPaymentIntentStatusEnum.CREATE_FAILED,
        last_error_code="creating_stale",
    )


def reserve_crypto_intent_or_read_winner(
    *,
    initiator_id: int,
    purchase_kind: str,
    product_code: str,
    rub_amount: Decimal,
    public_id: UUID,
) -> tuple[CryptoPaymentIntent, bool]:
    try:
        with transaction.atomic():
            intent = create_crypto_intent(
                initiator_id=initiator_id,
                purchase_kind=purchase_kind,
                product_code=product_code,
                rub_amount=rub_amount,
                public_id=public_id,
            )
    except IntegrityError:
        winner = CryptoPaymentIntent.objects.filter(
            initiator_id=initiator_id,
            purchase_kind=purchase_kind,
            status__in=(
                CryptoPaymentIntentStatusEnum.CREATING,
                CryptoPaymentIntentStatusEnum.ACTIVE,
            ),
        ).first()
        if winner is None:
            raise
        return winner, False
    return intent, True


def fail_crypto_intent_creation(*, intent_id: int, error_code: str) -> int:
    return conditionally_transition_crypto_intent(
        intent_id=intent_id,
        from_statuses=(CryptoPaymentIntentStatusEnum.CREATING,),
        to_status=CryptoPaymentIntentStatusEnum.CREATE_FAILED,
        updates={"last_error_code": error_code},
    )


def activate_crypto_intent_from_provider(
    *, intent_id: int, invoice: CryptoInvoiceDTO
) -> CryptoPaymentIntent | None:
    updated_rows = conditionally_transition_crypto_intent(
        intent_id=intent_id,
        from_statuses=(CryptoPaymentIntentStatusEnum.CREATING,),
        to_status=CryptoPaymentIntentStatusEnum.ACTIVE,
        updates={
            "provider_invoice_id": invoice.invoice_id,
            "provider_invoice_url": invoice.bot_invoice_url,
            "provider_created_at": invoice.created_at,
            "provider_expires_at": invoice.expiration_date,
            "last_error_code": "",
        },
    )
    if updated_rows != 1:
        return None
    return CryptoPaymentIntent.objects.get(pk=intent_id)


def get_reusable_platega_intent(
    *, initiator_id: int, purchase_kind: str, now: datetime
) -> PlategaPaymentIntent | None:
    return PlategaPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=PlategaPaymentIntentStatusEnum.ACTIVE,
        provider_expires_at__gt=now,
    ).first()


def get_blocking_platega_intent(
    *, initiator_id: int, purchase_kind: str
) -> PlategaPaymentIntent | None:
    return PlategaPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status__in=(
            PlategaPaymentIntentStatusEnum.CREATING,
            PlategaPaymentIntentStatusEnum.PROCESSING,
            PlategaPaymentIntentStatusEnum.RETRYABLE,
        ),
    ).first()


def expire_active_platega_intent(
    *, initiator_id: int, purchase_kind: str, now: datetime
) -> int:
    return PlategaPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=PlategaPaymentIntentStatusEnum.ACTIVE,
        provider_expires_at__lte=now,
    ).update(status=PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED, updated_at=now)


def fail_stale_creating_platega_intent(
    *, initiator_id: int, purchase_kind: str, stale_before: datetime
) -> int:
    return PlategaPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=PlategaPaymentIntentStatusEnum.CREATING,
        created_at__lte=stale_before,
    ).update(
        status=PlategaPaymentIntentStatusEnum.CREATE_FAILED,
        last_error_code="creating_stale",
    )


def create_platega_intent(
    *,
    initiator_id: int,
    purchase_kind: str,
    product_code: str,
    rub_amount: Decimal,
    public_id: UUID,
) -> PlategaPaymentIntent:
    return PlategaPaymentIntent.objects.create(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        product_code=product_code,
        rub_amount=rub_amount,
        public_id=public_id,
    )


def reserve_platega_intent_or_read_winner(
    *,
    initiator_id: int,
    purchase_kind: str,
    product_code: str,
    rub_amount: Decimal,
    public_id: UUID,
) -> tuple[PlategaPaymentIntent, bool]:
    try:
        with transaction.atomic():
            intent = create_platega_intent(
                initiator_id=initiator_id,
                purchase_kind=purchase_kind,
                product_code=product_code,
                rub_amount=rub_amount,
                public_id=public_id,
            )
    except IntegrityError:
        winner = PlategaPaymentIntent.objects.filter(
            initiator_id=initiator_id,
            purchase_kind=purchase_kind,
            status__in=(
                PlategaPaymentIntentStatusEnum.CREATING,
                PlategaPaymentIntentStatusEnum.ACTIVE,
            ),
        ).first()
        if winner is None:
            raise
        return winner, False
    return intent, True


def fail_platega_intent_creation(*, intent_id: int, error_code: str) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        status=PlategaPaymentIntentStatusEnum.CREATING,
    ).update(
        status=PlategaPaymentIntentStatusEnum.CREATE_FAILED,
        last_error_code=error_code,
    )


def activate_platega_intent_from_provider(
    *,
    intent_id: int,
    transaction: PlategaTransactionDTO,
    expires_at: datetime,
) -> PlategaPaymentIntent | None:
    updated_rows = PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        status=PlategaPaymentIntentStatusEnum.CREATING,
    ).update(
        status=PlategaPaymentIntentStatusEnum.ACTIVE,
        provider_transaction_id=transaction.transaction_id,
        provider_payment_url=transaction.redirect_url,
        provider_expires_at=expires_at,
        last_error_code="",
        updated_at=expires_at,
    )
    if updated_rows == 1:
        return PlategaPaymentIntent.objects.get(pk=intent_id)
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        status=PlategaPaymentIntentStatusEnum.ACTIVE,
        provider_transaction_id=transaction.transaction_id,
        provider_payment_url=transaction.redirect_url,
        provider_expires_at=expires_at,
    ).first()


def get_platega_intent_by_provider_transaction_id(
    *, provider_transaction_id: UUID
) -> PlategaPaymentIntent | None:
    return (
        PlategaPaymentIntent.objects.select_related("initiator", "payment")
        .filter(provider_transaction_id=provider_transaction_id)
        .first()
    )


def cancel_platega_intent(*, intent_id: int, canceled_at: datetime) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        status__in=(
            PlategaPaymentIntentStatusEnum.ACTIVE,
            PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED,
        ),
    ).update(
        status=PlategaPaymentIntentStatusEnum.PROVIDER_CANCELED,
        updated_at=canceled_at,
    )


def get_platega_intent_by_id(*, intent_id: int) -> PlategaPaymentIntent | None:
    return (
        PlategaPaymentIntent.objects.select_related("initiator", "payment")
        .filter(pk=intent_id)
        .first()
    )


def get_platega_intent_for_notification(
    *, intent_id: int
) -> PlategaPaymentIntent | None:
    return (
        PlategaPaymentIntent.objects.select_related(
            "initiator",
            "payment",
            "payment__key",
            "payment__gift_certificate",
            "payment__apple_cashback_purchase",
            "payment__user__vpn_subscription",
        )
        .filter(
            pk=intent_id,
            payment__isnull=False,
            status=PlategaPaymentIntentStatusEnum.FULFILLED,
            notification_queued_at__isnull=False,
            notification_sent_at__isnull=True,
        )
        .first()
    )


def mark_platega_notification_sent(*, intent_id: int, sent_at: datetime) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        status=PlategaPaymentIntentStatusEnum.FULFILLED,
        notification_sent_at__isnull=True,
    ).update(notification_sent_at=sent_at, updated_at=sent_at)


def claim_platega_intent_for_fulfillment(
    *, intent_id: int, attempted_at: datetime
) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        payment__isnull=True,
        status__in=(
            PlategaPaymentIntentStatusEnum.ACTIVE,
            PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED,
            PlategaPaymentIntentStatusEnum.RETRYABLE,
        ),
    ).update(
        status=PlategaPaymentIntentStatusEnum.PROCESSING,
        fulfillment_attempted_at=attempted_at,
        updated_at=attempted_at,
    )


def finalize_platega_intent_fulfillment(
    *, intent_id: int, payment_id: int, fulfilled_at: datetime
) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        payment__isnull=True,
        status=PlategaPaymentIntentStatusEnum.PROCESSING,
    ).update(
        payment_id=payment_id,
        fulfilled_at=fulfilled_at,
        status=PlategaPaymentIntentStatusEnum.FULFILLED,
        last_error_code="",
        updated_at=fulfilled_at,
    )


def mark_platega_intent_retryable(*, intent_id: int, error_code: str) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        payment__isnull=True,
        status__in=(
            PlategaPaymentIntentStatusEnum.ACTIVE,
            PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED,
            PlategaPaymentIntentStatusEnum.PROCESSING,
            PlategaPaymentIntentStatusEnum.RETRYABLE,
        ),
    ).update(
        status=PlategaPaymentIntentStatusEnum.RETRYABLE,
        last_error_code=error_code,
    )


def claim_platega_notification_enqueue(
    *, intent_id: int, queued_at: datetime
) -> int:
    return PlategaPaymentIntent.objects.filter(
        Q(purchase_kind=PaymentKindEnum.VPN_SUBSCRIPTION)
        | Q(payment__apple_cashback_purchase__rate_percent__isnull=False),
        pk=intent_id,
        status=PlategaPaymentIntentStatusEnum.FULFILLED,
        notification_queued_at__isnull=True,
    ).update(notification_queued_at=queued_at, updated_at=queued_at)


def clear_platega_notification_enqueue(
    *, intent_id: int, queued_at: datetime
) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        status=PlategaPaymentIntentStatusEnum.FULFILLED,
        notification_queued_at=queued_at,
    ).update(notification_queued_at=None)
