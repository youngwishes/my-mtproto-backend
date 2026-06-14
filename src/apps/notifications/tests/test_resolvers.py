from __future__ import annotations

from django.test import TestCase

from apps.notifications.enums import ContextResolverType
from apps.notifications.resolvers import resolve_context
from apps.users.tests.factories import SystemUserFactory


class TestResolveContext(TestCase):
    def test_none_resolver_returns_empty_dict(self) -> None:
        user = SystemUserFactory()
        result = resolve_context(resolver_type=ContextResolverType.NONE, user=user)
        self.assertEqual(result, {})
