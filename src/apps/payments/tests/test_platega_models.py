from __future__ import annotations

from uuid import uuid4

from django.db import models
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.payments.enums import (
    PaymentKindEnum,
    PaymentProviderEnum,
    PlategaPaymentIntentStatusEnum,
)
from apps.payments.models import PlategaPaymentIntent
from apps.payments.tests.factories import PaymentFactory, PlategaPaymentIntentFactory


class TestPlategaPaymentIntentModel(TestCase):
    def test_statuses_and_live_pair_constraint_match_approved_lifecycle(self) -> None:
        user = PlategaPaymentIntentFactory().initiator
        PlategaPaymentIntent.objects.all().delete()

        self.assertEqual(
            tuple(PlategaPaymentIntentStatusEnum),
            (
                PlategaPaymentIntentStatusEnum.CREATING,
                PlategaPaymentIntentStatusEnum.ACTIVE,
                PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED,
                PlategaPaymentIntentStatusEnum.PROCESSING,
                PlategaPaymentIntentStatusEnum.RETRYABLE,
                PlategaPaymentIntentStatusEnum.PROVIDER_CANCELED,
                PlategaPaymentIntentStatusEnum.CREATE_FAILED,
                PlategaPaymentIntentStatusEnum.FULFILLED,
            ),
        )

        for existing, candidate, is_allowed in (
            (
                PlategaPaymentIntentStatusEnum.CREATING,
                PlategaPaymentIntentStatusEnum.ACTIVE,
                False,
            ),
            (
                PlategaPaymentIntentStatusEnum.ACTIVE,
                PlategaPaymentIntentStatusEnum.CREATING,
                False,
            ),
            (
                PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED,
                PlategaPaymentIntentStatusEnum.ACTIVE,
                True,
            ),
            (
                PlategaPaymentIntentStatusEnum.PROVIDER_CANCELED,
                PlategaPaymentIntentStatusEnum.CREATING,
                True,
            ),
            (
                PlategaPaymentIntentStatusEnum.CREATE_FAILED,
                PlategaPaymentIntentStatusEnum.ACTIVE,
                True,
            ),
        ):
            with self.subTest(existing=existing, candidate=candidate):
                PlategaPaymentIntent.objects.all().delete()
                PlategaPaymentIntentFactory(
                    initiator=user,
                    purchase_kind=PaymentKindEnum.SUBSCRIPTION,
                    status=existing,
                )
                if is_allowed:
                    PlategaPaymentIntentFactory(
                        initiator=user,
                        purchase_kind=PaymentKindEnum.SUBSCRIPTION,
                        status=candidate,
                    )
                else:
                    with self.assertRaises(IntegrityError), transaction.atomic():
                        PlategaPaymentIntentFactory(
                            initiator=user,
                            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
                            status=candidate,
                        )

    def test_provider_transaction_and_payment_are_unique_identities(self) -> None:
        intent = PlategaPaymentIntentFactory(
            status=PlategaPaymentIntentStatusEnum.FULFILLED,
            provider_transaction_id="f8ea17f7-33bd-4a76-b2e6-f37d67eb512d",
            payment=PaymentFactory(provider=PaymentProviderEnum.PLATEGA),
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            PlategaPaymentIntentFactory(
                provider_transaction_id=intent.provider_transaction_id,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlategaPaymentIntentFactory(payment=intent.payment)

    def test_fields_keep_expected_payment_contract_defaults(self) -> None:
        intent = PlategaPaymentIntentFactory()

        self.assertEqual(intent.currency, "RUB")
        self.assertEqual(intent.payment_method, 2)
        self.assertFalse(
            PlategaPaymentIntent._meta.get_field("public_id").editable
        )

    def test_complete_model_field_and_relationship_contract(self) -> None:
        fields = {field.name: field for field in PlategaPaymentIntent._meta.fields}

        self.assertEqual(
            tuple(fields),
            (
                "id", "is_active", "created_at", "updated_at", "public_id",
                "initiator", "purchase_kind", "product_code", "rub_amount",
                "currency", "payment_method", "status", "provider_transaction_id",
                "provider_payment_url", "provider_expires_at", "fulfillment_attempted_at",
                "fulfilled_at", "notification_queued_at", "notification_sent_at",
                "payment", "last_error_code",
            ),
        )
        self.assertIsInstance(fields["id"], models.BigAutoField)
        self.assertTrue(fields["id"].primary_key)
        self.assertIsInstance(fields["is_active"], models.BooleanField)
        self.assertTrue(fields["is_active"].default)
        self.assertIsInstance(fields["created_at"], models.DateTimeField)
        self.assertTrue(fields["created_at"].auto_now_add)
        self.assertTrue(fields["created_at"].null)
        self.assertIsInstance(fields["updated_at"], models.DateTimeField)
        self.assertTrue(fields["updated_at"].auto_now)
        self.assertTrue(fields["updated_at"].null)
        self.assertIsInstance(fields["public_id"], models.UUIDField)
        self.assertTrue(fields["public_id"].unique)
        self.assertFalse(fields["public_id"].editable)
        self.assertIs(fields["public_id"].default, uuid4)
        self.assertIsInstance(fields["initiator"], models.ForeignKey)
        self.assertIs(fields["initiator"].remote_field.on_delete, models.PROTECT)
        self.assertEqual(fields["initiator"].remote_field.related_name, "platega_payment_intents")
        self.assertFalse(fields["initiator"].null)
        self.assertFalse(fields["initiator"].blank)
        self.assertIsInstance(fields["purchase_kind"], models.CharField)
        self.assertEqual(fields["purchase_kind"].max_length, 32)
        self.assertEqual(tuple(fields["purchase_kind"].choices), tuple(PaymentKindEnum.choices()))
        self.assertIsInstance(fields["product_code"], models.CharField)
        self.assertEqual(fields["product_code"].max_length, 32)
        self.assertIsInstance(fields["rub_amount"], models.DecimalField)
        self.assertEqual((fields["rub_amount"].max_digits, fields["rub_amount"].decimal_places), (10, 2))
        self.assertFalse(fields["rub_amount"].null)
        self.assertIsInstance(fields["currency"], models.CharField)
        self.assertEqual((fields["currency"].max_length, fields["currency"].default), (3, "RUB"))
        self.assertIsInstance(fields["payment_method"], models.PositiveSmallIntegerField)
        self.assertEqual(fields["payment_method"].default, 2)
        self.assertIsInstance(fields["status"], models.CharField)
        self.assertEqual(fields["status"].max_length, 32)
        self.assertEqual(fields["status"].default, PlategaPaymentIntentStatusEnum.CREATING)
        self.assertEqual(tuple(fields["status"].choices), tuple(PlategaPaymentIntentStatusEnum.choices()))
        self.assertIsInstance(fields["provider_transaction_id"], models.UUIDField)
        self.assertTrue(fields["provider_transaction_id"].unique)
        self.assertTrue(fields["provider_transaction_id"].null)
        self.assertTrue(fields["provider_transaction_id"].blank)
        self.assertIsInstance(fields["provider_payment_url"], models.URLField)
        self.assertEqual(fields["provider_payment_url"].max_length, 512)
        self.assertTrue(fields["provider_payment_url"].blank)
        self.assertFalse(fields["provider_payment_url"].null)
        for field_name in (
            "provider_expires_at", "fulfillment_attempted_at", "fulfilled_at",
            "notification_queued_at", "notification_sent_at",
        ):
            with self.subTest(field=field_name):
                self.assertIsInstance(fields[field_name], models.DateTimeField)
                self.assertTrue(fields[field_name].null)
                self.assertTrue(fields[field_name].blank)
        self.assertIsInstance(fields["payment"], models.OneToOneField)
        self.assertIs(fields["payment"].remote_field.on_delete, models.PROTECT)
        self.assertEqual(fields["payment"].remote_field.related_name, "platega_intent")
        self.assertTrue(fields["payment"].null)
        self.assertTrue(fields["payment"].blank)
        self.assertIsInstance(fields["last_error_code"], models.CharField)
        self.assertEqual((fields["last_error_code"].max_length, fields["last_error_code"].blank), (64, True))
        self.assertFalse(fields["last_error_code"].null)
