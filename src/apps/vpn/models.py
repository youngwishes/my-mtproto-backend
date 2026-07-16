from __future__ import annotations

import secrets
import uuid

from django.core.validators import MaxValueValidator, MinLengthValidator, MinValueValidator
from django.db import models

from apps.core import BaseDjangoModel
from apps.vpn.enums import (
    VPNAccessState,
    VPNApplyStatus,
    VPNNodeHealthState,
    VPNRealityFingerprint,
    VPNRealityFlow,
)
from apps.vpn.validators import (
    validate_agent_secret_lookup_key,
    validate_https_base_url,
    validate_optional_sha256,
    validate_public_host,
    validate_reality_short_id,
    validate_sni,
    validate_x25519_public_key,
)


def generate_subscription_token() -> str:
    """Return a URL-safe token backed by 256 random bits."""
    return secrets.token_urlsafe(32)


class VPNAccess(BaseDjangoModel):
    user = models.OneToOneField(
        "users.SystemUser",
        on_delete=models.CASCADE,
        related_name="vpn_access",
        verbose_name="пользователь",
    )
    subscription_token = models.CharField(
        "subscription token",
        max_length=128,
        unique=True,
        default=generate_subscription_token,
        editable=False,
        validators=[MinLengthValidator(43)],
    )
    desired_uuid = models.UUIDField("желаемый UUID", default=uuid.uuid4)
    desired_revision = models.PositiveBigIntegerField("желаемая revision", default=1)
    published_uuid = models.UUIDField("опубликованный UUID", null=True, blank=True)
    published_revision = models.PositiveBigIntegerField(
        "опубликованная revision", null=True, blank=True
    )
    expired_at = models.DateTimeField("действует до")
    state = models.CharField(
        "состояние",
        max_length=32,
        choices=VPNAccessState.choices(),
        default=VPNAccessState.PREPARING,
    )
    state_revision = models.PositiveBigIntegerField("revision состояния", default=1)
    ready_notification_revision = models.PositiveBigIntegerField(
        "последняя уведомлённая revision", default=0
    )
    disabled_at = models.DateTimeField("отключён", null=True, blank=True)
    disabled_reason = models.CharField("причина отключения", max_length=128, blank=True)
    disabled_by = models.ForeignKey(
        "users.SystemUser",
        on_delete=models.SET_NULL,
        related_name="vpn_accesses_disabled",
        verbose_name="отключил",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "VPN-доступ"
        verbose_name_plural = "VPN-доступы"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(desired_revision__gte=1),
                name="vpn_access_desired_revision_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(state_revision__gte=1),
                name="vpn_access_state_revision_gte_1",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(published_uuid__isnull=True, published_revision__isnull=True)
                    | models.Q(published_uuid__isnull=False, published_revision__isnull=False)
                ),
                name="vpn_access_published_pair",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(published_revision__isnull=True)
                    | models.Q(published_revision__lte=models.F("desired_revision"))
                ),
                name="vpn_access_published_lte_desired",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(published_revision__isnull=True)
                    | models.Q(published_revision__lt=models.F("desired_revision"))
                    | models.Q(published_uuid=models.F("desired_uuid"))
                ),
                name="vpn_access_published_uuid_matches_revision",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(state=VPNAccessState.READY)
                    | models.Q(
                        published_uuid__isnull=False,
                        published_uuid=models.F("desired_uuid"),
                        published_revision=models.F("desired_revision"),
                    )
                ),
                name="vpn_access_ready_is_current",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(state=VPNAccessState.DISABLED_REFUND)
                    | (
                        models.Q(disabled_at__isnull=False, disabled_by__isnull=False)
                        & ~models.Q(disabled_reason="")
                    )
                ),
                name="vpn_access_refund_has_audit",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(published_revision__isnull=False)
                    & models.Q(
                        ready_notification_revision__lte=models.F("published_revision")
                    )
                    | models.Q(ready_notification_revision=0)
                ),
                name="vpn_access_notification_lte_published",
            ),
        ]

    def __str__(self) -> str:
        return f"VPNAccess #{self.pk} — {self.user_id}"


class VPNPurchase(BaseDjangoModel):
    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="vpn_purchase",
        verbose_name="платёж",
    )
    access = models.ForeignKey(
        VPNAccess,
        on_delete=models.PROTECT,
        related_name="purchases",
        verbose_name="VPN-доступ",
    )
    period_days = models.PositiveSmallIntegerField(
        "оплаченный период, дней", default=30, validators=[MinValueValidator(1)]
    )
    expired_at_after = models.DateTimeField("срок после применения платежа")

    class Meta:
        verbose_name = "VPN-покупка"
        verbose_name_plural = "VPN-покупки"


class VPNNode(BaseDjangoModel):
    name = models.CharField("имя", max_length=64, unique=True)
    number = models.PositiveSmallIntegerField("порядковый номер", unique=True)
    location = models.CharField("локация", max_length=128)
    host = models.CharField("публичный host", max_length=255, validators=[validate_public_host])
    port = models.PositiveIntegerField(
        "публичный порт", validators=[MinValueValidator(1), MaxValueValidator(65535)]
    )
    agent_base_url = models.URLField(
        "HTTPS URL агента", max_length=255, validators=[validate_https_base_url]
    )
    agent_secret_key = models.CharField(
        "lookup key секрета", max_length=128, validators=[validate_agent_secret_lookup_key]
    )
    agent_contract_version = models.CharField("версия контракта агента", max_length=16)
    health_state = models.CharField(
        "health state",
        max_length=32,
        choices=VPNNodeHealthState.choices(),
        default=VPNNodeHealthState.NEW,
    )
    is_access_available = models.BooleanField("доступна для выдачи", default=True)
    desired_snapshot_revision = models.PositiveBigIntegerField(
        "желаемая snapshot revision", default=0
    )
    desired_snapshot_hash = models.CharField(
        "желаемый snapshot hash",
        max_length=64,
        blank=True,
        validators=[validate_optional_sha256],
    )
    applied_snapshot_revision = models.PositiveBigIntegerField(
        "применённая snapshot revision", default=0
    )
    applied_snapshot_hash = models.CharField(
        "применённый snapshot hash",
        max_length=64,
        blank=True,
        validators=[validate_optional_sha256],
    )
    last_health_at = models.DateTimeField("последний health check", null=True, blank=True)
    last_error_code = models.CharField("последний код ошибки", max_length=64, blank=True)
    reality_public_key = models.CharField(
        "REALITY public key", max_length=64, validators=[validate_x25519_public_key]
    )
    reality_short_id = models.CharField(
        "REALITY short ID", max_length=16, validators=[validate_reality_short_id]
    )
    reality_server_name = models.CharField(
        "REALITY SNI", max_length=253, validators=[validate_sni]
    )
    reality_fingerprint = models.CharField(
        "REALITY fingerprint",
        max_length=16,
        choices=VPNRealityFingerprint.choices(),
        default=VPNRealityFingerprint.CHROME,
    )
    reality_flow = models.CharField(
        "VLESS flow",
        max_length=32,
        choices=VPNRealityFlow.choices(),
        default=VPNRealityFlow.XTLS_RPRX_VISION,
    )

    class Meta:
        ordering = ["number"]
        verbose_name = "VPN-нода"
        verbose_name_plural = "VPN-ноды"
        constraints = [
            models.UniqueConstraint(
                fields=("host", "port"), name="uniq_vpn_node_public_authority"
            ),
            models.CheckConstraint(
                condition=models.Q(applied_snapshot_revision__lte=models.F("desired_snapshot_revision")),
                name="vpn_node_applied_snapshot_lte_desired",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(desired_snapshot_revision=0, desired_snapshot_hash="")
                    | (
                        models.Q(desired_snapshot_revision__gt=0)
                        & ~models.Q(desired_snapshot_hash="")
                    )
                ),
                name="vpn_node_desired_snapshot_pair",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(applied_snapshot_revision=0, applied_snapshot_hash="")
                    | (
                        models.Q(applied_snapshot_revision__gt=0)
                        & ~models.Q(applied_snapshot_hash="")
                    )
                ),
                name="vpn_node_applied_snapshot_pair",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(health_state=VPNNodeHealthState.READY)
                    | (
                        models.Q(desired_snapshot_revision__gt=0)
                        & models.Q(
                            applied_snapshot_revision=models.F(
                                "desired_snapshot_revision"
                            ),
                            applied_snapshot_hash=models.F("desired_snapshot_hash"),
                        )
                        & ~models.Q(desired_snapshot_hash="")
                    )
                ),
                name="vpn_node_ready_snapshot_exact",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class VPNAccessNodeApply(BaseDjangoModel):
    access = models.ForeignKey(
        VPNAccess,
        on_delete=models.CASCADE,
        related_name="node_applies",
        verbose_name="VPN-доступ",
    )
    node = models.ForeignKey(
        VPNNode,
        on_delete=models.CASCADE,
        related_name="access_applies",
        verbose_name="VPN-нода",
    )
    desired_revision = models.PositiveBigIntegerField("желаемая revision")
    applied_revision = models.PositiveBigIntegerField(
        "применённая revision", null=True, blank=True
    )
    status = models.CharField(
        "статус",
        max_length=16,
        choices=VPNApplyStatus.choices(),
        default=VPNApplyStatus.PENDING,
    )
    last_attempt_at = models.DateTimeField("последняя попытка", null=True, blank=True)
    last_error_code = models.CharField("последний код ошибки", max_length=64, blank=True)

    class Meta:
        verbose_name = "применение VPN-доступа на ноде"
        verbose_name_plural = "применения VPN-доступов на нодах"
        constraints = [
            models.UniqueConstraint(
                fields=("access", "node"), name="uniq_vpn_access_node_apply"
            ),
            models.CheckConstraint(
                condition=models.Q(desired_revision__gte=1),
                name="vpn_apply_desired_revision_gte_1",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(applied_revision__isnull=True)
                    | models.Q(applied_revision__lte=models.F("desired_revision"))
                ),
                name="vpn_apply_applied_lte_desired",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(status=VPNApplyStatus.APPLIED)
                    | models.Q(applied_revision=models.F("desired_revision"))
                ),
                name="vpn_apply_status_has_exact_revision",
            ),
        ]
