from __future__ import annotations

import secrets
import string
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
from apps.payments.exceptions import (
    BadPaymentData,
    GiftCertificateAlreadyActivated,
    GiftCertificateExpired,
    GiftCertificateNotFound,
)
from apps.payments.models import GiftCertificate
from apps.payments.selectors.common import (
    get_active_product_by_code,
    get_payment_user_for_update,
)
from apps.payments.selectors.apples import (
    count_apple_cashback_purchases,
    create_apple_cashback_purchase,
    get_apple_cashback_purchase_by_identity,
)
from apps.payments.selectors.gifts import (
    create_gift_certificate,
    create_gift_certificate_payment,
    get_gift_certificate_by_payment_identity,
    get_gift_certificate_by_code,
    normalize_gift_certificate_code,
)
from apps.payments.services.dtos import (
    ActivateGiftCertificateOut,
    ApplePurchaseOutcomeDTO,
    CreateGiftCertificateOut,
    HistoricalPurchaseReplayDTO,
)
from apps.payments.services.extend_key_service import (
    ExtendKeyService,
    get_extend_key_service,
)
from apps.users.selectors import get_user_by_username
from apps.vds.selectors import get_active_key
from apps.vds.services import IssueKeyService, get_issue_key_on_commit_service

if TYPE_CHECKING:
    from apps.payments.models import AppleCashbackPurchase
    from apps.payments.services.dtos import (
        ActivateGiftCertificateIn,
        CreateGiftCertificateIn,
        CreateGiftCertificateResult,
    )


_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_RANDOM_LENGTH = 8
_MAX_CODE_GENERATION_ATTEMPTS = 10


def _generate_certificate_code() -> str:
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_RANDOM_LENGTH))
    return f"KEY-{raw[:4]}-{raw[4:]}"


def _saved_gift_loyalty_outcome(
    *, purchase: AppleCashbackPurchase
) -> ApplePurchaseOutcomeDTO:
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


def _saved_gift_result(
    *, purchase: AppleCashbackPurchase, username: str
) -> CreateGiftCertificateResult:
    if purchase.payment.user.username != username:
        raise BadPaymentData(telegram_id=username)
    if purchase.rate_percent is None:
        return HistoricalPurchaseReplayDTO()
    certificate = get_gift_certificate_by_payment_identity(
        provider=purchase.payment.provider,
        charge_id=purchase.payment.charge_id,
    )
    if certificate is None:
        raise BadPaymentData(telegram_id=username)
    return CreateGiftCertificateOut(
        code=certificate.code,
        loyalty=_saved_gift_loyalty_outcome(purchase=purchase),
    )


def _gift_nominal_rub_amount(*, certificate: CreateGiftCertificateIn) -> Decimal:
    if certificate.nominal_rub_amount is not None:
        amount = Decimal(certificate.nominal_rub_amount)
        if amount <= 0:
            raise BadPaymentData(telegram_id=certificate.username)
        return amount

    product = get_active_product_by_code(code=ProductCodeEnum.MTPROTO_30D)
    if product is None or product.currency != "RUB":
        raise BadPaymentData(telegram_id=certificate.username)
    kopecks = Decimal(product.price)
    if kopecks <= 0 or kopecks != kopecks.to_integral_value():
        raise BadPaymentData(telegram_id=certificate.username)
    return (kopecks / Decimal("100")).quantize(Decimal("0.01"))


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CreateGiftCertificateService:
    """Create a paid gift certificate and its loyalty outcome atomically."""

    @log_service_error
    def __call__(
        self, *, certificate: CreateGiftCertificateIn
    ) -> CreateGiftCertificateResult:
        if not certificate.charge_id.strip():
            raise BadPaymentData(telegram_id=certificate.username)
        identity_key = build_apple_purchase_identity_key(
            provider=certificate.provider,
            charge_id=certificate.charge_id,
            kind=PaymentKindEnum.GIFT_CERTIFICATE,
        )

        for _ in range(_MAX_CODE_GENERATION_ATTEMPTS):
            code = _generate_certificate_code()
            try:
                with transaction.atomic():
                    user = get_payment_user_for_update(username=certificate.username)
                    if user is None:
                        raise BadPaymentData(telegram_id=certificate.username)
                    existing = get_apple_cashback_purchase_by_identity(
                        identity_key=identity_key
                    )
                    if existing is not None:
                        return _saved_gift_result(
                            purchase=existing,
                            username=certificate.username,
                        )

                    nominal_rub_amount = _gift_nominal_rub_amount(
                        certificate=certificate
                    )
                    eligible_purchase_count = count_apple_cashback_purchases(
                        user_id=user.pk
                    )
                    rate_percent = get_apple_level(
                        eligible_purchase_count=eligible_purchase_count
                    ).rate_percent
                    payment = create_gift_certificate_payment(
                        user_id=user.pk,
                        charge_id=certificate.charge_id,
                        provider=certificate.provider,
                    )
                    gift_certificate = create_gift_certificate(
                        code=code,
                        buyer_id=user.pk,
                        payment_id=payment.pk,
                        expires_at=timezone.now() + timedelta(days=365),
                    )
                    apples_earned = calculate_apples(
                        nominal_rub_amount=nominal_rub_amount,
                        rate_percent=rate_percent,
                    )
                    balance_after = user.apple_balance + apples_earned
                    purchase = create_apple_cashback_purchase(
                        payment_id=payment.pk,
                        identity_key=identity_key,
                        rate_percent=rate_percent,
                        apples_earned=apples_earned,
                        balance_after=balance_after,
                        eligible_purchase_count_after=eligible_purchase_count + 1,
                        result_expired_at=None,
                    )
                    user.apple_balance = balance_after
                    user.save(update_fields=["apple_balance"])
                    return CreateGiftCertificateOut(
                        code=gift_certificate.code,
                        loyalty=_saved_gift_loyalty_outcome(purchase=purchase),
                    )
            except IntegrityError:
                winner = get_apple_cashback_purchase_by_identity(
                    identity_key=identity_key
                )
                if winner is not None:
                    return _saved_gift_result(
                        purchase=winner,
                        username=certificate.username,
                    )
                continue

        raise BadPaymentData(telegram_id=certificate.username)


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ActivateGiftCertificateService:
    """Активирует подарочный сертификат на 30 дней подписки."""

    extend_key_service: ExtendKeyService
    issue_key_service: IssueKeyService

    @log_service_error
    def __call__(
        self, *, activation: ActivateGiftCertificateIn
    ) -> ActivateGiftCertificateOut:
        user = get_user_by_username(username=activation.username)
        if user is None:
            raise BadPaymentData(telegram_id=activation.username)

        code = normalize_gift_certificate_code(code=activation.code)

        expired_certificate = False
        with transaction.atomic():
            certificate = get_gift_certificate_by_code(code=code)
            if certificate is None:
                raise GiftCertificateNotFound(telegram_id=activation.username, code=code)
            if certificate.status == GiftCertificate.Status.ACTIVATED:
                raise GiftCertificateAlreadyActivated(
                    telegram_id=activation.username,
                    code=code,
                )
            if (
                certificate.status == GiftCertificate.Status.EXPIRED
                or certificate.expires_at <= timezone.now()
            ):
                if certificate.status != GiftCertificate.Status.EXPIRED:
                    certificate.status = GiftCertificate.Status.EXPIRED
                    certificate.save(update_fields=["status"])
                expired_certificate = True
            else:
                activated_at = timezone.now()
                reserved_count = GiftCertificate.objects.filter(
                    pk=certificate.pk,
                    status=GiftCertificate.Status.CREATED,
                    activated_by__isnull=True,
                    activated_at__isnull=True,
                ).update(
                    status=GiftCertificate.Status.ACTIVATED,
                    activated_by=user,
                    activated_at=activated_at,
                )
                if reserved_count == 0:
                    raise GiftCertificateAlreadyActivated(
                        telegram_id=activation.username,
                        code=code,
                    )

                active_key = get_active_key(user=user)
                if active_key is None:
                    key = self.issue_key_service(
                        user=user,
                        expired_date=timezone.now()
                        + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
                    )
                else:
                    self.extend_key_service(key=active_key)
                    key = active_key

        if expired_certificate:
            raise GiftCertificateExpired(telegram_id=activation.username, code=code)

        return ActivateGiftCertificateOut(
            expired_date=key.expired_date.date().strftime("%d.%m.%y"),
        )


def get_create_gift_certificate_service() -> CreateGiftCertificateService:
    return CreateGiftCertificateService()


def get_activate_gift_certificate_service() -> ActivateGiftCertificateService:
    return ActivateGiftCertificateService(
        extend_key_service=get_extend_key_service(),
        issue_key_service=get_issue_key_on_commit_service(),
    )
