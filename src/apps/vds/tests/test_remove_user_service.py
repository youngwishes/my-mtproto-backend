from unittest import TestCase
from unittest.mock import patch

from apps.vds.models import MTPRotoKey
from apps.vds.services import get_remove_user_key_service
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestRemoveUserService(TestCase):
    def setUp(self) -> None:
        self.mtproto_key = MTPRotoKeyFactory()

    @patch("apps.vds.services.remove_key_from_vds.requests.post")
    def test_remove_key_service(self, mock_post) -> None:
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertTrue(self.mtproto_key.is_active)
        self.assertFalse(self.mtproto_key.was_deleted)

        get_remove_user_key_service()(keys=MTPRotoKey.objects.all())

        mock_post.assert_called_once_with(
            f"{self.mtproto_key.vds.url}/api/v1/remove-user",
            json={'usernames': [self.mtproto_key.user.username]},
            timeout=8,
        )

        self.mtproto_key.refresh_from_db()
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertFalse(self.mtproto_key.is_active)
        self.assertTrue(self.mtproto_key.was_deleted)
