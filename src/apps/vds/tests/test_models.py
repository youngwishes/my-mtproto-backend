from __future__ import annotations

from django.test import TestCase

from apps.vds.selectors import get_least_populated_vds
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestVDSQuerySet(TestCase):
    def test_get_least_populated_excludes_is_keys_available_false(self) -> None:
        VDSInstanceFactory(is_keys_available=False)
        available = VDSInstanceFactory(is_keys_available=True)

        result = get_least_populated_vds()

        self.assertEqual(result, available)

    def test_get_least_populated_picks_least_loaded_among_available(self) -> None:
        server_1 = VDSInstanceFactory(is_keys_available=True)
        server_2 = VDSInstanceFactory(is_keys_available=True)
        for _ in range(3):
            MTPRotoKeyFactory(vds=server_1)

        result = get_least_populated_vds()

        self.assertEqual(result, server_2)

    def test_get_least_populated_returns_none_when_all_have_keys_unavailable(self) -> None:
        VDSInstanceFactory(is_keys_available=False)

        result = get_least_populated_vds()

        self.assertIsNone(result)
