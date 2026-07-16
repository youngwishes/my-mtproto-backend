from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion


def copy_legacy_evidence(apps, schema_editor) -> None:
    legacy_model = apps.get_model("vpn", "VPNAccessNodeApply")
    history_model = apps.get_model("vpn", "VPNAccessNodeRevisionEvidence")
    node_model = apps.get_model("vpn", "VPNNode")
    for row in legacy_model.objects.all().iterator():
        history_model.objects.create(
            access_id=row.access_id,
            node_id=row.node_id,
            revision=row.desired_revision,
            applied_revision=row.applied_revision,
            status=row.status,
            is_serving=row.status == "applied" and row.applied_revision == row.desired_revision,
            last_attempt_at=row.last_attempt_at,
            last_error_code=row.last_error_code,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    serving_node_ids = history_model.objects.filter(
        is_active=True, is_serving=True
    ).values_list("node_id", flat=True)
    node_model.objects.filter(pk__in=serving_node_ids).update(
        data_plane_state="serving_ready"
    )


class Migration(migrations.Migration):
    dependencies = [("vpn", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="vpnnode",
            name="data_plane_state",
            field=models.CharField(
                choices=[("serving_ready", "Data plane готов"), ("unavailable", "Data plane недоступен")],
                default="unavailable",
                max_length=32,
                verbose_name="состояние data plane",
            ),
        ),
        migrations.CreateModel(
            name="VPNAccessNodeRevisionEvidence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True, verbose_name="активность")),
                ("created_at", models.DateTimeField(auto_now_add=True, null=True, verbose_name="дата создания")),
                ("updated_at", models.DateTimeField(auto_now=True, null=True, verbose_name="дата обновления")),
                ("revision", models.PositiveBigIntegerField()),
                ("applied_revision", models.PositiveBigIntegerField(blank=True, null=True)),
                ("status", models.CharField(choices=[("pending", "Ожидает"), ("applied", "Применено"), ("failed", "Ошибка")], default="pending", max_length=16)),
                ("is_serving", models.BooleanField(default=False)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("last_error_code", models.CharField(blank=True, max_length=64)),
                ("access", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revision_evidences", to="vpn.vpnaccess")),
                ("node", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revision_evidences", to="vpn.vpnnode")),
            ],
        ),
        migrations.AddConstraint(
            model_name="vpnaccessnoderevisionevidence",
            constraint=models.UniqueConstraint(fields=("access", "node", "revision"), name="uniq_vpn_access_node_revision_evidence"),
        ),
        migrations.AddConstraint(
            model_name="vpnaccessnoderevisionevidence",
            constraint=models.CheckConstraint(condition=models.Q(("revision__gte", 1)), name="vpn_revision_evidence_revision_gte_1"),
        ),
        migrations.AddConstraint(
            model_name="vpnaccessnoderevisionevidence",
            constraint=models.CheckConstraint(
                condition=(~models.Q(status="applied") | models.Q(applied_revision=models.F("revision"))),
                name="vpn_revision_evidence_applied_exact",
            ),
        ),
        migrations.RunPython(copy_legacy_evidence, migrations.RunPython.noop),
    ]
