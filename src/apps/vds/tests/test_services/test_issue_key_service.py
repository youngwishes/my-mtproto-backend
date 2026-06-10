from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.services import get_issue_key_service
from apps.vds.tests.factories import VDSInstanceFactory


class TestIssueKeyService(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.expired_date = timezone.now() + timedelta(days=30)

    def test_raises_when_no_vds_available(self) -> None:
        VDSInstanceFactory(is_keys_available=False)

        from apps.vds.exceptions import NoVDSAvailable
        with self.assertRaises(NoVDSAvailable):
            get_issue_key_service()(user=self.user, expired_date=self.expired_date)
