from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

import responses
from django.test import TestCase
from django.utils import timezone

from apps.vds.services import get_sync_keys_to_vds_infra_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestSyncKeysToVdsInfraService(TestCase):
    def setUp(self) -> None:
        self.target = VDSInstanceFactory()

    def _mock_target_endpoint(self, status: int = 200) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.target.internal_url}/api/users",
            json={"status": "ok"},
            status=status,
        )

    @responses.activate
    def test_posts_active_valid_key_to_target(self) -> None:
        key = MTPRotoKeyFactory(expired_date=timezone.now() + timedelta(days=30))
        self._mock_target_endpoint()

        get_sync_keys_to_vds_infra_service()(instance_id=self.target.pk)

        self.assertEqual(len(responses.calls), 1)
        body = json.loads(responses.calls[0].request.body)
        self.assertEqual(body["username"], key.user.username)
        self.assertEqual(body["secret"], str(key.token))

    @responses.activate
    def test_does_not_post_expired_key(self) -> None:
        MTPRotoKeyFactory(expired_date=timezone.now() - timedelta(days=1))

        get_sync_keys_to_vds_infra_service()(instance_id=self.target.pk)

        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_does_not_post_deleted_key(self) -> None:
        MTPRotoKeyFactory(
            was_deleted=True,
            expired_date=timezone.now() + timedelta(days=30),
        )

        get_sync_keys_to_vds_infra_service()(instance_id=self.target.pk)

        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_does_not_post_inactive_key(self) -> None:
        MTPRotoKeyFactory(
            is_active=False,
            expired_date=timezone.now() + timedelta(days=30),
        )

        get_sync_keys_to_vds_infra_service()(instance_id=self.target.pk)

        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_skips_key_without_token(self) -> None:
        MTPRotoKeyFactory(token="", expired_date=timezone.now() + timedelta(days=30))

        get_sync_keys_to_vds_infra_service()(instance_id=self.target.pk)

        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_skips_key_without_username(self) -> None:
        MTPRotoKeyFactory(
            user__username="",
            expired_date=timezone.now() + timedelta(days=30),
        )

        get_sync_keys_to_vds_infra_service()(instance_id=self.target.pk)

        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_multiple_keys_all_posted(self) -> None:
        MTPRotoKeyFactory(expired_date=timezone.now() + timedelta(days=30))
        MTPRotoKeyFactory(expired_date=timezone.now() + timedelta(days=30))
        self._mock_target_endpoint()

        get_sync_keys_to_vds_infra_service()(instance_id=self.target.pk)

        self.assertEqual(len(responses.calls), 2)

    @responses.activate
    def test_continues_on_http_error_and_notifies_admin(self) -> None:
        MTPRotoKeyFactory(expired_date=timezone.now() + timedelta(days=30))
        MTPRotoKeyFactory(expired_date=timezone.now() + timedelta(days=30))
        responses.add(
            method=responses.POST,
            url=f"{self.target.internal_url}/api/users",
            json={"error": "fail"},
            status=500,
        )
        self._mock_target_endpoint()

        with patch("apps.vds.services.sync_keys_to_vds_infra_service.send_telegram_message"):
            get_sync_keys_to_vds_infra_service()(instance_id=self.target.pk)

        self.assertEqual(len(responses.calls), 2)
