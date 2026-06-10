from __future__ import annotations

from datetime import timedelta
from unittest import mock

import responses
from django.test import TestCase
from django.utils import timezone

from apps.vds.services import get_update_key_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


@mock.patch("apps.notifications.services.send_notification_service.send_telegram_message")
@mock.patch("apps.core.decorators._log_service_error")
@mock.patch("apps.core.decorators._log_infra_error")
class TestUpdateKeyServiceVDSSelection(TestCase):
    def setUp(self) -> None:
        self.future = timezone.now() + timedelta(days=30)

    @responses.activate
    @mock.patch("apps.vds.services.update_key_infra_service.update_key_on_another_vds_instances_task")
    def test_stays_on_same_vds_when_available(
        self, mock_task, mock_log_infra, mock_log_service, mock_send
    ) -> None:
        vds = VDSInstanceFactory(is_keys_available=True)
        key = MTPRotoKeyFactory(vds=vds, expired_date=self.future)
        responses.add(
            method=responses.PATCH,
            url=f"{vds.internal_url}/api/users",
            json={"key": "new_token", "tls_domain": "new.domain"},
        )

        get_update_key_service()(username=str(key.user.username))

        key.refresh_from_db()
        self.assertEqual(key.vds_id, vds.pk)
        self.assertEqual(key.node_number, vds.name)
        self.assertEqual(key.token, "new_token")

    @responses.activate
    @mock.patch("apps.vds.services.update_key_infra_service.update_key_on_another_vds_instances_task")
    def test_migrates_to_new_vds_when_current_has_keys_unavailable(
        self, mock_task, mock_log_infra, mock_log_service, mock_send
    ) -> None:
        old_vds = VDSInstanceFactory(is_keys_available=False)
        new_vds = VDSInstanceFactory(is_keys_available=True)
        key = MTPRotoKeyFactory(vds=old_vds, expired_date=self.future)
        responses.add(
            method=responses.PATCH,
            url=f"{new_vds.internal_url}/api/users",
            json={"key": "migrated_token", "tls_domain": "migrated.domain"},
        )

        get_update_key_service()(username=str(key.user.username))

        key.refresh_from_db()
        self.assertEqual(key.vds_id, new_vds.pk)
        self.assertEqual(key.node_number, new_vds.name)
        self.assertEqual(key.token, "migrated_token")
        self.assertEqual(key.tls_domain, "migrated.domain")

    @responses.activate
    @mock.patch("apps.vds.services.update_key_infra_service.update_key_on_another_vds_instances_task")
    def test_patch_is_sent_to_selected_vds_not_old_vds(
        self, mock_task, mock_log_infra, mock_log_service, mock_send
    ) -> None:
        old_vds = VDSInstanceFactory(is_keys_available=False)
        new_vds = VDSInstanceFactory(is_keys_available=True)
        key = MTPRotoKeyFactory(vds=old_vds, expired_date=self.future)
        responses.add(
            method=responses.PATCH,
            url=f"{new_vds.internal_url}/api/users",
            json={"key": "migrated_token", "tls_domain": "migrated.domain"},
        )

        get_update_key_service()(username=str(key.user.username))

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            f"{new_vds.internal_url}/api/users",
        )

    def test_raises_when_no_vds_available(
        self, mock_log_infra, mock_log_service, mock_send
    ) -> None:
        # All VDS have is_keys_available=False → get_least_populated_vds() returns None
        vds = VDSInstanceFactory(is_keys_available=False)
        key = MTPRotoKeyFactory(vds=vds, expired_date=self.future)

        from apps.vds.exceptions import NoVDSAvailable
        with self.assertRaises(NoVDSAvailable):
            get_update_key_service()(username=str(key.user.username))
