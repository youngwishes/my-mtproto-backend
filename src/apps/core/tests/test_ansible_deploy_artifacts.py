from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase


class TestAnsibleDeployArtifacts(SimpleTestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        playbook_path = repo_root / "ansible" / "deploy.yml"
        group_vars_path = repo_root / "ansible" / "group_vars" / "beatvault.yml.example"
        inventory_path = repo_root / "ansible" / "inventory" / "production.ini.example"
        compose_path = repo_root / "docker-compose.yml"

        self.assertTrue(playbook_path.exists(), "ansible/deploy.yml is missing")
        self.assertTrue(group_vars_path.exists(), "group_vars must match the beatvault inventory group")
        self.content = playbook_path.read_text(encoding="utf-8")
        self.group_vars_content = group_vars_path.read_text(encoding="utf-8")
        self.inventory_content = inventory_path.read_text(encoding="utf-8")
        self.compose_content = compose_path.read_text(encoding="utf-8")

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

    def test_inventory_uses_the_production_ssh_user(self) -> None:
        self.assertIn("ansible_user=root", self.inventory_content)

    def test_deploy_protects_environment_files(self) -> None:
        self.assertIn("Protect production environment files", self.content)
        self.assertIn('mode: "0600"', self.content)
        self.assertIn('"{{ deploy_root }}/.env"', self.content)
        self.assertIn('"{{ deploy_root }}/bot/.env"', self.content)

    def test_deploy_enables_automatic_certificate_renewal(self) -> None:
        self.assertIn("certbot", self.content)
        self.assertIn("name: certbot.timer", self.content)
        self.assertIn("enabled: true", self.content)
        self.assertIn("certbot.service.override.conf.j2", self.content)

        repo_root = Path(__file__).resolve().parents[4]
        override_path = repo_root / "ansible" / "templates" / "certbot.service.override.conf.j2"
        override = override_path.read_text(encoding="utf-8")
        self.assertIn("certbot/certbot", override)
        self.assertIn("{{ deploy_root }}/certbot/conf:/etc/letsencrypt", override)
        self.assertIn("{{ deploy_root }}/certbot/www:/var/www/certbot", override)
        self.assertIn("docker exec nginx nginx -s reload", override)

    def test_public_services_restart_after_host_reboot(self) -> None:
        for service in ("django", "nginx"):
            match = re.search(
                rf"^  {service}:\n(?P<body>(?:    .*\n|\n)+?)(?=^  \S|\Z)",
                self.compose_content,
                flags=re.MULTILINE,
            )
            self.assertIsNotNone(match)
            service_definition = match.group("body")
            self.assertIn("restart: unless-stopped", service_definition)

    def test_failed_deploy_rolls_back_to_previous_revision(self) -> None:
        self.assertIn("Capture current Git revision", self.content)
        self.assertIn("rescue:", self.content)
        self.assertIn("Rollback Git revision", self.content)
        self.assertIn("deploy_previous_revision.stdout", self.content)

    def test_deploy_requires_every_compose_service_to_be_running(self) -> None:
        self.assertIn("Check running compose services", self.content)
        self.assertIn("deploy_required_services | difference", self.content)
