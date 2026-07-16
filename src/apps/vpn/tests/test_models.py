from __future__ import annotations

from datetime import timedelta
import base64
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from apps.core.models import BaseDjangoModel
from apps.payments.tests.factories import PaymentFactory
from apps.vpn.enums import VPNAccessState, VPNApplyStatus
from apps.vpn.models import VPNAccess, VPNAccessNodeApply, VPNNode, VPNPurchase
from apps.vpn.tests.factories import (
    VPNAccessFactory,
    VPNAccessNodeApplyFactory,
    VPNNodeFactory,
    VPNPurchaseFactory,
)


class VPNModelStructureTests(TestCase):
    def test_all_domain_models_inherit_base_model(self) -> None:
        for model in (VPNAccess, VPNPurchase, VPNNode, VPNAccessNodeApply):
            self.assertTrue(issubclass(model, BaseDjangoModel))

    def test_private_reality_data_is_not_in_schema(self) -> None:
        fields = {field.name for field in VPNNode._meta.get_fields()}
        self.assertNotIn("reality_private_key", fields)
        self.assertNotIn("reality_target", fields)
        self.assertNotIn("agent_secret", fields)
        self.assertIn("agent_secret_key", fields)


class VPNAccessTests(TestCase):
    def test_token_and_uuid_are_stable_when_other_fields_change(self) -> None:
        access = VPNAccessFactory()
        token = access.subscription_token
        desired_uuid = access.desired_uuid

        access.expired_at += timedelta(days=30)
        access.save()
        access.refresh_from_db()

        self.assertEqual(access.subscription_token, token)
        self.assertEqual(access.desired_uuid, desired_uuid)
        self.assertGreaterEqual(len(token), 43)

    def test_one_access_per_user_and_unique_token(self) -> None:
        access = VPNAccessFactory()
        with self.assertRaises(IntegrityError), transaction.atomic():
            VPNAccessFactory(user=access.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            VPNAccessFactory(subscription_token=access.subscription_token)

    def test_published_revision_cannot_exceed_desired_revision(self) -> None:
        access = VPNAccessFactory()
        access.published_uuid = uuid4()
        access.published_revision = 2
        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_published_uuid_and_revision_must_be_set_together(self) -> None:
        access = VPNAccessFactory()
        access.published_uuid = uuid4()
        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_ready_access_requires_published_credential(self) -> None:
        access = VPNAccessFactory()
        access.state = VPNAccessState.READY
        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_ready_access_requires_current_desired_revision(self) -> None:
        access = VPNAccessFactory()
        access.state = VPNAccessState.READY
        access.desired_revision = 2
        access.published_uuid = uuid4()
        access.published_revision = 1
        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_ready_access_requires_published_uuid_to_match_desired_uuid(self) -> None:
        access = VPNAccessFactory()
        access.state = VPNAccessState.READY
        access.published_uuid = uuid4()
        access.published_revision = access.desired_revision

        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_ready_access_uuid_match_is_enforced_by_database(self) -> None:
        access = VPNAccessFactory()
        access.state = VPNAccessState.READY
        access.published_uuid = uuid4()
        access.published_revision = access.desired_revision

        with self.assertRaises(IntegrityError), transaction.atomic():
            access.save()

    def test_preparing_access_allows_staged_reissue(self) -> None:
        access = VPNAccessFactory()
        previous_uuid = access.desired_uuid
        access.published_uuid = previous_uuid
        access.published_revision = 1
        access.desired_uuid = uuid4()
        access.desired_revision = 2
        access.state = VPNAccessState.PREPARING

        access.full_clean()

    def test_equal_published_revision_requires_desired_uuid_for_any_state(self) -> None:
        for state in (VPNAccessState.PREPARING, VPNAccessState.EXPIRED):
            with self.subTest(state=state):
                access = VPNAccessFactory()
                access.state = state
                access.published_revision = access.desired_revision
                access.published_uuid = uuid4()

                with self.assertRaises(ValidationError):
                    access.full_clean()

    def test_equal_revision_uuid_match_is_enforced_by_database_for_any_state(self) -> None:
        for state in (VPNAccessState.PREPARING, VPNAccessState.EXPIRED):
            with self.subTest(state=state):
                access = VPNAccessFactory()
                access.state = state
                access.published_revision = access.desired_revision
                access.published_uuid = uuid4()

                with self.assertRaises(IntegrityError), transaction.atomic():
                    access.save()

    def test_null_published_pair_is_valid_while_preparing(self) -> None:
        access = VPNAccessFactory(state=VPNAccessState.PREPARING)

        access.full_clean()

    def test_state_revision_starts_at_one(self) -> None:
        access = VPNAccessFactory()
        access.state_revision = 0
        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_refund_state_requires_audit_fields(self) -> None:
        access = VPNAccessFactory()
        access.state = VPNAccessState.DISABLED_REFUND
        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_ready_notification_revision_cannot_exceed_published(self) -> None:
        access = VPNAccessFactory()
        access.ready_notification_revision = 1
        with self.assertRaises(ValidationError):
            access.full_clean()


class VPNPurchaseTests(TestCase):
    def test_payment_can_be_fulfilled_only_once(self) -> None:
        purchase = VPNPurchaseFactory()
        with self.assertRaises(IntegrityError), transaction.atomic():
            VPNPurchaseFactory(payment=purchase.payment)

    def test_purchase_keeps_refund_audit_even_if_access_is_archived(self) -> None:
        payment = PaymentFactory()
        purchase = VPNPurchaseFactory(payment=payment, period_days=30)
        self.assertEqual(purchase.period_days, 30)
        self.assertEqual(purchase.payment_id, payment.pk)
        self.assertIsNotNone(purchase.expired_at_after)


class VPNNodeValidationTests(TestCase):
    def assert_invalid(self, **changes: object) -> None:
        node = VPNNodeFactory.build(**changes)
        with self.assertRaises(ValidationError):
            node.full_clean()

    def test_accepts_dns_ipv4_and_ipv6_hosts(self) -> None:
        for host in ("vpn.example.com", "203.0.113.7", "2001:db8::7"):
            node = VPNNodeFactory.build(host=host)
            node.full_clean()

    def test_rejects_invalid_host_and_sni(self) -> None:
        self.assert_invalid(host="https://vpn.example.com/path")
        self.assert_invalid(reality_server_name="not a host")
        self.assert_invalid(reality_server_name="127.0.0.1")

    def test_validates_https_agent_url_and_lookup_key(self) -> None:
        self.assert_invalid(agent_base_url="http://agent.example.com")
        self.assert_invalid(agent_secret_key="actual-secret-token-value")

    def test_agent_url_is_exact_origin_without_trailing_slash(self) -> None:
        for value in (
            "https://agent.example.com/",
            "https://agent.example.com//",
            "https://agent.example.com/path",
        ):
            with self.subTest(value=value):
                self.assert_invalid(agent_base_url=value)

    def test_validates_port(self) -> None:
        self.assert_invalid(port=0)
        self.assert_invalid(port=65536)

    def test_validates_x25519_public_key(self) -> None:
        self.assert_invalid(reality_public_key="too-short")
        self.assert_invalid(reality_public_key="!" * 43)

    def test_x25519_public_key_rejects_standard_base64_alphabet(self) -> None:
        canonical = VPNNodeFactory.reality_public_key
        self.assert_invalid(reality_public_key=canonical.replace("-", "+"))
        self.assert_invalid(reality_public_key=canonical.replace("_", "/"))

    def test_x25519_public_key_rejects_noncanonical_pad_bits(self) -> None:
        canonical = base64.urlsafe_b64encode(bytes(32)).decode().rstrip("=")
        noncanonical = f"{canonical[:-1]}B"
        self.assertEqual(
            base64.urlsafe_b64decode(f"{canonical}="),
            base64.urlsafe_b64decode(f"{noncanonical}="),
        )

        self.assert_invalid(reality_public_key=noncanonical)

    def test_validates_even_hex_short_id_up_to_sixteen_chars(self) -> None:
        for value in ("0", "xyz1", "a" * 18):
            self.assert_invalid(reality_short_id=value)
        for value in ("ab", "0123456789abcdef"):
            VPNNodeFactory.build(reality_short_id=value).full_clean()

    def test_rejects_unsupported_fingerprint_and_flow(self) -> None:
        self.assert_invalid(reality_fingerprint="firefox")
        self.assert_invalid(reality_flow="none")

    def test_snapshot_revision_and_hash_must_be_set_together(self) -> None:
        self.assert_invalid(desired_snapshot_revision=1, desired_snapshot_hash="")
        self.assert_invalid(desired_snapshot_revision=0, desired_snapshot_hash="a" * 64)
        self.assert_invalid(applied_snapshot_revision=1, applied_snapshot_hash="")
        self.assert_invalid(applied_snapshot_revision=0, applied_snapshot_hash="a" * 64)

    def test_ready_node_requires_exact_nonzero_snapshot(self) -> None:
        for fields in (
            {
                "health_state": "ready",
                "desired_snapshot_revision": 0,
                "desired_snapshot_hash": "",
                "applied_snapshot_revision": 0,
                "applied_snapshot_hash": "",
            },
            {
                "health_state": "ready",
                "desired_snapshot_revision": 2,
                "desired_snapshot_hash": "a" * 64,
                "applied_snapshot_revision": 1,
                "applied_snapshot_hash": "a" * 64,
            },
            {
                "health_state": "ready",
                "desired_snapshot_revision": 1,
                "desired_snapshot_hash": "a" * 64,
                "applied_snapshot_revision": 1,
                "applied_snapshot_hash": "b" * 64,
            },
        ):
            self.assert_invalid(**fields)

    def test_ready_node_exact_snapshot_is_enforced_by_database(self) -> None:
        node = VPNNodeFactory()
        node.health_state = "ready"

        with self.assertRaises(IntegrityError), transaction.atomic():
            node.save()

    def test_non_ready_node_allows_staged_snapshot(self) -> None:
        node = VPNNodeFactory.build(
            health_state="syncing",
            desired_snapshot_revision=2,
            desired_snapshot_hash="b" * 64,
            applied_snapshot_revision=1,
            applied_snapshot_hash="a" * 64,
        )

        node.full_clean()

    def test_unique_name_number_and_public_authority(self) -> None:
        node = VPNNodeFactory()
        for fields in (
            {"name": node.name},
            {"number": node.number},
            {"host": node.host, "port": node.port},
        ):
            with self.assertRaises(IntegrityError), transaction.atomic():
                VPNNodeFactory(**fields)


class VPNAccessNodeApplyTests(TestCase):
    def test_access_node_pair_is_unique(self) -> None:
        apply = VPNAccessNodeApplyFactory()
        with self.assertRaises(IntegrityError), transaction.atomic():
            VPNAccessNodeApplyFactory(access=apply.access, node=apply.node)

    def test_applied_status_requires_exact_desired_revision(self) -> None:
        apply = VPNAccessNodeApplyFactory()
        apply.desired_revision = 2
        apply.applied_revision = 1
        apply.status = VPNApplyStatus.APPLIED
        with self.assertRaises(ValidationError):
            apply.full_clean()

    def test_applied_revision_cannot_exceed_desired_revision(self) -> None:
        apply = VPNAccessNodeApplyFactory()
        apply.desired_revision = 1
        apply.applied_revision = 2
        apply.status = VPNApplyStatus.FAILED
        with self.assertRaises(ValidationError):
            apply.full_clean()
