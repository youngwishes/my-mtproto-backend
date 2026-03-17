import json

import responses
from django.test import TestCase

from apps.vds.models import MTPRotoKey
from apps.vds.services import get_remove_user_key_service
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestRemoveUserService(TestCase):
    def setUp(self) -> None:
        self.mtproto_key = MTPRotoKeyFactory()

    def _add_response(self):
        responses.add(
            method=responses.POST,
            url=self.mtproto_key.vds.internal_url + "/api/v1/remove-user",
        )

    @responses.activate
    def test_remove_key_service(self) -> None:
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertTrue(self.mtproto_key.is_active)
        self.assertFalse(self.mtproto_key.was_deleted)
        self._add_response()

        get_remove_user_key_service()(keys=MTPRotoKey.objects.all())

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            self.mtproto_key.vds.internal_url + "/api/v1/remove-user",
        )
        self.assertEqual(responses.calls[0].request.method, "POST")
        request_body = json.loads(responses.calls[0].request.body)
        self.assertEqual(
            request_body.get("usernames"), [self.mtproto_key.user.username]
        )

        self.mtproto_key.refresh_from_db()
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertFalse(self.mtproto_key.is_active)
        self.assertTrue(self.mtproto_key.was_deleted)
