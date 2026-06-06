from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.notifications.enums import ContextResolverType
from apps.notifications.resolvers import resolve_context
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestResolveContext(TestCase):
    def test_none_resolver_returns_empty_dict(self) -> None:
        user = SystemUserFactory()
        result = resolve_context(resolver_type=ContextResolverType.NONE, user=user)
        self.assertEqual(result, {})

    def test_active_key_link_returns_link(self) -> None:
        user = SystemUserFactory()
        vds = VDSInstanceFactory()
        key = MTPRotoKeyFactory(
            user=user, vds=vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
        )
        result = resolve_context(resolver_type=ContextResolverType.ACTIVE_KEY_LINK, user=user)
        self.assertIsNotNone(result)
        self.assertEqual(result["link"], key.get_proxy_link())

    def test_active_key_link_returns_none_when_no_key(self) -> None:
        user = SystemUserFactory()
        result = resolve_context(resolver_type=ContextResolverType.ACTIVE_KEY_LINK, user=user)
        self.assertIsNone(result)
