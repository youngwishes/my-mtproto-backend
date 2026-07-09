from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, final

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.decorators import log_service_error
from apps.payments.enums import PaymentKindEnum
from apps.payments.exceptions import (
    BadPaymentData,
    GiftCertificateAlreadyActivated,
    GiftCertificateExpired,
    GiftCertificateNotFound,
)
from apps.payments.models import GiftCertificate, Payment
from apps.payments.selectors import (
    get_gift_certificate_by_payment_identity,
    get_gift_certificate_by_code,
    normalize_gift_certificate_code,
)
from apps.payments.services.dtos import (
    ActivateGiftCertificateOut,
    CreateGiftCertificateOut,
)
from apps.payments.services.extend_key_service import (
    ExtendKeyService,
    get_extend_key_service,
)
from apps.users.selectors import get_user_by_username
from apps.vds.selectors import get_active_key
from apps.vds.services import IssueKeyService, get_issue_key_on_commit_service

if TYPE_CHECKING:
    from apps.payments.services.dtos import (
        ActivateGiftCertificateIn,
        CreateGiftCertificateIn,
    )


_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_RANDOM_LENGTH = 8
_MAX_CODE_GENERATION_ATTEMPTS = 10


def _generate_certificate_code() -> str:
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_RANDOM_LENGTH))
    return f"KEY-{raw[:4]}-{raw[4:]}"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CreateGiftCertificateService:
    """Создаёт одноразовый подарочный сертификат после успешной оплаты."""

    @log_service_error
    def __call__(
        self, *, certificate: CreateGiftCertificateIn
    ) -> CreateGiftCertificateOut:
        user = get_user_by_username(username=certificate.username)
        if user is None:
            raise BadPaymentData(telegram_id=certificate.username)

        existing_certificate = get_gift_certificate_by_payment_identity(
            provider=certificate.provider,
            charge_id=certificate.charge_id,
        )
        if existing_certificate is not None:
            return CreateGiftCertificateOut(code=existing_certificate.code)

        for _ in range(_MAX_CODE_GENERATION_ATTEMPTS):
            code = _generate_certificate_code()
            try:
                with transaction.atomic():
                    payment = Payment.objects.create(
                        user=user,
                        key=None,
                        charge_id=certificate.charge_id,
                        provider=certificate.provider,
                        kind=PaymentKindEnum.GIFT_CERTIFICATE,
                    )
                    gift_certificate = GiftCertificate.objects.create(
                        code=code,
                        buyer=user,
                        payment=payment,
                        expires_at=timezone.now() + timedelta(days=365),
                    )
                return CreateGiftCertificateOut(code=gift_certificate.code)
            except IntegrityError:
                existing_certificate = get_gift_certificate_by_payment_identity(
                    provider=certificate.provider,
                    charge_id=certificate.charge_id,
                )
                if existing_certificate is not None:
                    return CreateGiftCertificateOut(code=existing_certificate.code)
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
