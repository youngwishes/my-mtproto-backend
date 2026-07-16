from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from apps.users.models import SystemUser


class VPNRevisionEvidenceExpandMigrationTest(TransactionTestCase):
    migrate_from = ("vpn", "0001_initial")
    migrate_to = ("vpn", "0002_revision_evidence_expand")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        self.old_apps = self.executor.loader.project_state([self.migrate_from]).apps

    def tearDown(self) -> None:
        MigrationExecutor(connection).migrate([self.migrate_to])
        super().tearDown()

    def _legacy_rows(self):
        user = SystemUser.objects.create(username="migration-vpn-user")
        access_model = self.old_apps.get_model("vpn", "VPNAccess")
        node_model = self.old_apps.get_model("vpn", "VPNNode")
        apply_model = self.old_apps.get_model("vpn", "VPNAccessNodeApply")
        credential = uuid.uuid4()
        access = access_model.objects.create(
            user_id=user.pk,
            subscription_token="x" * 43,
            desired_uuid=credential,
            desired_revision=1,
            published_uuid=credential,
            published_revision=1,
            expired_at=timezone.now() + timedelta(days=30),
            state="ready",
            state_revision=1,
        )
        node = node_model.objects.create(
            name="migration-node",
            number=1,
            location="Migration",
            host="migration.example.com",
            port=443,
            agent_base_url="https://agent.example.com",
            agent_secret_key="VPN_MIGRATION_TOKEN",
            agent_contract_version="v1",
            health_state="ready",
            desired_snapshot_revision=1,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=1,
            applied_snapshot_hash="a" * 64,
            reality_public_key="UEnA5W5Lk_7-ywBVKfM8kS4DFwQ6F6-y9vDSS2rQYF8",
            reality_short_id="abcd",
            reality_server_name="example.com",
        )
        apply = apply_model.objects.create(
            access_id=access.pk,
            node_id=node.pk,
            desired_revision=1,
            applied_revision=1,
            status="applied",
        )
        return access, node, apply_model, apply

    def test_forward_old_writer_multiple_history_and_reverse_are_safe(self) -> None:
        access, node, old_apply_model, legacy = self._legacy_rows()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        new_apps = self.executor.loader.project_state([self.migrate_to]).apps
        history = new_apps.get_model("vpn", "VPNAccessNodeRevisionEvidence")
        self.assertTrue(history.objects.get(revision=1).is_serving)
        self.assertEqual(
            new_apps.get_model("vpn", "VPNNode").objects.get(pk=node.pk).data_plane_state,
            "serving_ready",
        )

        old_apply_model.objects.update_or_create(
            access_id=access.pk,
            node_id=node.pk,
            defaults={
                "desired_revision": 2,
                "applied_revision": None,
                "status": "pending",
            },
        )
        next_uuid = uuid.uuid4()
        self.old_apps.get_model("vpn", "VPNAccess").objects.filter(pk=access.pk).update(
            desired_uuid=next_uuid,
            desired_revision=2,
            published_uuid=next_uuid,
            published_revision=2,
            state="ready",
        )
        self.old_apps.get_model("vpn", "VPNNode").objects.filter(pk=node.pk).update(
            desired_snapshot_revision=2,
            desired_snapshot_hash="b" * 64,
            applied_snapshot_revision=2,
            applied_snapshot_hash="b" * 64,
            health_state="ready",
        )
        old_apply_model.objects.filter(access_id=access.pk, node_id=node.pk).update(
            applied_revision=2, status="applied", is_active=True
        )
        from apps.vpn.models import VPNAccess
        from apps.vpn.selectors import get_subscription_nodes

        current_access = VPNAccess.objects.get(pk=access.pk)
        self.assertEqual(
            tuple(get_subscription_nodes(access=current_access).values_list("pk", flat=True)),
            (node.pk,),
        )
        history.objects.create(
            access_id=access.pk,
            node_id=node.pk,
            revision=3,
            status="pending",
        )
        self.assertEqual(history.objects.filter(access_id=access.pk).count(), 2)
        self.assertEqual(old_apply_model.objects.filter(access_id=access.pk).count(), 1)

        reverse = MigrationExecutor(connection)
        reverse.migrate([self.migrate_from])
        reversed_apps = reverse.loader.project_state([self.migrate_from]).apps
        coherent = reversed_apps.get_model("vpn", "VPNAccessNodeApply").objects.get(
            pk=legacy.pk
        )
        self.assertEqual(coherent.desired_revision, 2)
        self.assertEqual(coherent.status, "applied")
        self.assertNotIn(
            "vpn_vpnaccessnoderevisionevidence", connection.introspection.table_names()
        )
