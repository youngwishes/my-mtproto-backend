from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase


class TestAnsibleDeployArtifacts(SimpleTestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        playbook_path = repo_root / "ansible" / "deploy.yml"
        group_vars_path = repo_root / "ansible" / "group_vars" / "beatvault.yml.example"

        self.assertTrue(playbook_path.exists(), "ansible/deploy.yml is missing")
        self.assertTrue(group_vars_path.exists(), "group_vars must match the beatvault inventory group")
        self.content = playbook_path.read_text(encoding="utf-8")
        self.group_vars_content = group_vars_path.read_text(encoding="utf-8")

    def test_deploy_playbook_contains_in_place_healthcheck_flow(self) -> None:
        self.assertIn("/root/my-mtproto-backend", self.group_vars_content)
        self.assertIn("https://github.com/youngwishes/my-mtproto-backend.git", self.group_vars_content)
        self.assertIn("ansible.builtin.git", self.content)
        self.assertIn('version: "{{ deploy_revision }}"', self.content)
        self.assertIn("deploy_revision is match", self.content)
        self.assertNotIn("synchronize:", self.content)
        self.assertNotIn("delete: true", self.content)
        self.assertIn("docker compose -f docker-compose.yml -p", self.content)
        self.assertIn("up -d --build --remove-orphans", self.content)
        self.assertIn("uri:", self.content)
        self.assertIn("data/db.sqlite3", self.group_vars_content)
        self.assertIn("Refusing deploy because production SQLite database is missing", self.content)

    def test_deploy_preserves_production_state(self) -> None:
        self.assertNotIn("deploy_local_env_file", self.content)
        self.assertNotIn("deploy_local_bot_env_file", self.content)
        self.assertNotIn("ansible.builtin.copy", self.content)
        self.assertNotIn("git clean", self.content)
        self.assertNotIn("force: true", self.content)

    def test_deploy_relies_on_litestream_instead_of_local_sqlite_backup(self) -> None:
        self.assertNotIn("deploy_backups_path", self.content)
        self.assertNotIn(".backup", self.content)

    def test_healthcheck_requires_successful_root_response(self) -> None:
        self.assertIn("deploy_healthcheck_status_codes:\n  - 200", self.group_vars_content)
        self.assertNotIn("  - 404", self.group_vars_content)
