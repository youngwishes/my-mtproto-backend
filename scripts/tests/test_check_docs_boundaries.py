from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECKER = Path(__file__).parents[1] / "check_docs_boundaries.py"


class DocumentationBoundaryCheckTests(unittest.TestCase):
    def run_checker(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECKER), "--root", str(root)],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_release_command_outside_deploy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow = root / "docs" / "DEVELOPMENT_WORKFLOW.md"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "# Workflow\n\n"
                "```bash\n"
                "ansible-playbook -i inventory production/deploy.yml\n"
                "```\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("release commands belong to docs/DEPLOY.md", result.stdout)

    def test_release_command_in_root_readme_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text(
                "# Project\n\n"
                "ansible-playbook -i inventory production/deploy.yml\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("release commands belong to docs/DEPLOY.md", result.stdout)

    def test_multiline_release_command_outside_deploy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow = root / "docs" / "DEVELOPMENT_WORKFLOW.md"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "# Workflow\n\n"
                "```bash\n"
                "ansible-playbook -i inventory \\\n"
                "  ansible/deploy.yml \\\n"
                "  -e deploy_revision=abc123\n"
                "```\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("release commands belong to docs/DEPLOY.md", result.stdout)

    def test_inventory_service_smoke_outside_deploy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            architecture = root / "docs" / "ARCHITECTURE.md"
            architecture.parent.mkdir(parents=True)
            architecture.write_text(
                "# Architecture\n\n"
                "```bash\n"
                "ansible -i ansible/inventory/production.ini mtproto_keys \\\n"
                "  -m ansible.builtin.shell \\\n"
                "  -a 'git rev-parse HEAD && docker compose ps'\n"
                "```\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("release commands belong to docs/DEPLOY.md", result.stdout)

    def test_production_curl_smoke_outside_deploy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow = root / "docs" / "DEVELOPMENT_WORKFLOW.md"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "# Workflow\n\n"
                "See [deploy](DEPLOY.md).\n\n"
                "curl --fail https://dash.mtprotokeys.com/\n",
                encoding="utf-8",
            )
            (root / "docs" / "DEPLOY.md").write_text(
                "# Deploy\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("release commands belong to docs/DEPLOY.md", result.stdout)

    def test_nginx_smoke_outside_deploy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            architecture = root / "docs" / "ARCHITECTURE.md"
            architecture.parent.mkdir(parents=True)
            architecture.write_text(
                "# Architecture\n\n"
                "docker exec nginx nginx -t\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("release commands belong to docs/DEPLOY.md", result.stdout)

    def test_api_contract_outside_contracts_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payments = root / "docs" / "apps" / "PAYMENTS.md"
            payments.parent.mkdir(parents=True)
            payments.write_text(
                "# Payments\n\n"
                "## Зона ответственности\n\n"
                "### POST /api/v1/payments/example/\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("HTTP contracts belong to docs/CONTRACTS.md", result.stdout)

    def test_api_contract_in_app_map_bullet_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payments = root / "docs" / "apps" / "PAYMENTS.md"
            payments.parent.mkdir(parents=True)
            payments.write_text(
                "# Payments\n\n"
                "## Зона ответственности\n\n"
                "- POST /api/v1/payments/example/ creates an example.\n\n"
                "See [contracts](../CONTRACTS.md).\n",
                encoding="utf-8",
            )
            (root / "docs" / "CONTRACTS.md").write_text(
                "# Contracts\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("HTTP contracts belong to docs/CONTRACTS.md", result.stdout)

    def test_vds_contract_in_nested_readme_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            readme = root / "integration_tests" / "README.md"
            readme.parent.mkdir(parents=True)
            readme.write_text(
                "# Integration tests\n\n"
                "Verify the VDS state through GET/DELETE /api/users.\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("HTTP contracts belong to docs/CONTRACTS.md", result.stdout)

    def test_vds_contract_table_outside_contracts_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            architecture = root / "docs" / "ARCHITECTURE.md"
            architecture.parent.mkdir(parents=True)
            architecture.write_text(
                "# Architecture\n\n"
                "| Action | Method | URL |\n"
                "| --- | --- | --- |\n"
                "| Deliver | POST/PATCH | {server.internal_url}/api/users |\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("HTTP contracts belong to docs/CONTRACTS.md", result.stdout)

    def test_provider_contract_without_api_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            architecture = root / "docs" / "ARCHITECTURE.md"
            architecture.parent.mkdir(parents=True)
            architecture.write_text(
                "# Architecture\n\n"
                "POST {PLATEGA_BASE_URL}/transaction/process creates a payment.\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("HTTP contracts belong to docs/CONTRACTS.md", result.stdout)

    def test_vds_health_contract_without_api_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            vds = root / "docs" / "apps" / "VDS.md"
            vds.parent.mkdir(parents=True)
            vds.write_text(
                "# VDS\n\n## Зона ответственности\n\n"
                "Health probe uses GET {server.internal_url}.\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("HTTP contracts belong to docs/CONTRACTS.md", result.stdout)

    def test_json_contract_example_outside_contracts_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            business = root / "docs" / "BUSINESS.md"
            business.parent.mkdir(parents=True)
            business.write_text(
                "# Business\n\n"
                "HTTP response example:\n\n"
                "```json\n{\"status\": \"ok\"}\n```\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("HTTP contracts belong to docs/CONTRACTS.md", result.stdout)

    def test_non_wire_json_outside_contracts_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            architecture = root / "docs" / "ARCHITECTURE.md"
            architecture.parent.mkdir(parents=True)
            architecture.write_text(
                "# Architecture\n\n"
                "Internal worker configuration:\n\n"
                "```json\n{\"concurrency\": 2}\n```\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_telegram_callback_json_outside_contracts_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            architecture = root / "docs" / "ARCHITECTURE.md"
            architecture.parent.mkdir(parents=True)
            architecture.write_text(
                "# Architecture\n\n"
                "Internal Telegram callback configuration:\n\n"
                "```json\n{\"callback\": \"open_menu\"}\n```\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_internal_api_and_webhook_configuration_json_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            architecture = root / "docs" / "ARCHITECTURE.md"
            architecture.parent.mkdir(parents=True)
            architecture.write_text(
                "# Architecture\n\n"
                "Internal API client and webhook worker configuration:\n\n"
                "```json\n{\"timeout\": 5, \"retries\": 3}\n```\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_workflow_mechanics_outside_workflow_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agents = root / "AGENTS.md"
            agents.write_text(
                "# Agent instructions\n\n"
                "Increment scope_revision before redispatching task packets.\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "delivery workflow mechanics belong to docs/DEVELOPMENT_WORKFLOW.md",
            result.stdout,
        )

    def test_review_role_mechanics_outside_workflow_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            architecture = root / "docs" / "ARCHITECTURE.md"
            architecture.parent.mkdir(parents=True)
            architecture.write_text(
                "# Architecture\n\n"
                "The code-reviewer publishes gh pr review --comment and records "
                "VERDICT: approved.\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "delivery workflow mechanics belong to docs/DEVELOPMENT_WORKFLOW.md",
            result.stdout,
        )

    def test_feature_section_in_app_map_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payments = root / "docs" / "apps" / "PAYMENTS.md"
            payments.parent.mkdir(parents=True)
            payments.write_text(
                "# Payments\n\n"
                "## Зона ответственности\n\n"
                "Карта приложения.\n\n"
                "## Apple cashback\n\n"
                "Полное описание алгоритма.\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "app maps may only use canonical map sections",
            result.stdout,
        )

    def test_feature_subsection_in_app_map_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payments = root / "docs" / "apps" / "PAYMENTS.md"
            payments.parent.mkdir(parents=True)
            payments.write_text(
                "# Payments\n\n"
                "## Карта компонентов\n\n"
                "### Apple cashback\n\n"
                "Алгоритм фичи.\n\n"
                "See [business rules](../BUSINESS.md).\n",
                encoding="utf-8",
            )
            (root / "docs" / "BUSINESS.md").write_text(
                "# Business\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "app maps may only use canonical map sections",
            result.stdout,
        )

    def test_long_duplicate_prose_is_rejected(self) -> None:
        paragraph = (
            "Этот достаточно длинный абзац намеренно повторяет одну и ту же "
            "информацию сразу в двух канонических документах, поэтому проверка "
            "должна потребовать выбрать единственный источник истины и заменить "
            "второй экземпляр обычной ссылкой."
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "BUSINESS.md").write_text(
                f"# Business\n\n{paragraph}\n",
                encoding="utf-8",
            )
            (docs / "ARCHITECTURE.md").write_text(
                f"# Architecture\n\n{paragraph}\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate prose belongs in one canonical document", result.stdout)

    def test_long_duplicate_code_block_is_rejected(self) -> None:
        code = (
            "python manage.py example_command --with-a-long-option value\n"
            "python manage.py another_example --and-another-long-option value\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "BUSINESS.md").write_text(
                f"# Business\n\n```bash\n{code}```\n",
                encoding="utf-8",
            )
            (docs / "ARCHITECTURE.md").write_text(
                f"# Architecture\n\n```bash\n{code}```\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate code block belongs in one canonical document", result.stdout)

    def test_broken_local_markdown_link_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "BUSINESS.md").write_text(
                "# Business\n\nSee [missing owner](MISSING.md).\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("local Markdown link target does not exist", result.stdout)

    def test_broken_local_markdown_anchor_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "BUSINESS.md").write_text(
                "# Business\n\nSee [missing section](ARCHITECTURE.md#missing).\n",
                encoding="utf-8",
            )
            (docs / "ARCHITECTURE.md").write_text(
                "# Architecture\n\n## Existing section\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("local Markdown anchor does not exist", result.stdout)

    def test_broken_same_document_anchor_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "BUSINESS.md").write_text(
                "# Business\n\nSee [missing section](#missing).\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("local Markdown anchor does not exist", result.stdout)

    def test_existing_same_document_anchor_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "BUSINESS.md").write_text(
                "# Business\n\nSee [rules](#rules).\n\n## Rules\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_agents_without_canonical_workflow_link_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "AGENTS.md").write_text(
                "# Agent instructions\n\nFollow the repository conventions.\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "AGENTS.md must link to docs/DEVELOPMENT_WORKFLOW.md",
            result.stdout,
        )

    def test_agents_without_app_map_link_is_rejected(self) -> None:
        required = (
            "DEVELOPMENT_WORKFLOW.md",
            "BUSINESS.md",
            "ARCHITECTURE.md",
            "CONTRACTS.md",
            "MODELS.md",
            "DEPLOY.md",
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            docs = root / "docs"
            docs.mkdir()
            links: list[str] = []
            for name in required:
                body = (
                    "# Workflow\n\nSee [deploy](DEPLOY.md).\n"
                    if name == "DEVELOPMENT_WORKFLOW.md"
                    else f"# {name}\n"
                )
                (docs / name).write_text(body, encoding="utf-8")
                links.append(f"[{name}](docs/{name})")
            (root / "AGENTS.md").write_text(
                "# Agent instructions\n\n" + "\n".join(links) + "\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("AGENTS.md must link to docs/apps/", result.stdout)

    def test_workflow_without_deploy_link_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow = root / "docs" / "DEVELOPMENT_WORKFLOW.md"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "# Workflow\n\nDeploy requires separate permission.\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "DEVELOPMENT_WORKFLOW.md must link to DEPLOY.md",
            result.stdout,
        )

    def test_workflow_without_business_owner_link_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "DEVELOPMENT_WORKFLOW.md").write_text(
                "# Workflow\n\nSee [deploy](DEPLOY.md).\n",
                encoding="utf-8",
            )
            (docs / "DEPLOY.md").write_text("# Deploy\n", encoding="utf-8")

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "DEVELOPMENT_WORKFLOW.md must link to BUSINESS.md",
            result.stdout,
        )

    def test_app_map_without_canonical_document_link_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payments = root / "docs" / "apps" / "PAYMENTS.md"
            payments.parent.mkdir(parents=True)
            payments.write_text(
                "# Payments\n\n"
                "## Зона ответственности\n\n"
                "Карта приложения без ссылки на канонический документ.\n",
                encoding="utf-8",
            )

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "app map must link to ../BUSINESS.md",
            result.stdout,
        )

    def test_each_app_map_requires_its_relevant_canonical_links(self) -> None:
        required_by_app = {
            "CORE.md": ("../ARCHITECTURE.md", "../MODELS.md"),
            "INFRASTRUCTURE.md": ("../ARCHITECTURE.md", "../MODELS.md"),
            "MUSIC.md": ("../ARCHITECTURE.md",),
            "NOTIFICATIONS.md": ("../ARCHITECTURE.md", "../MODELS.md"),
            "PAYMENTS.md": (
                "../BUSINESS.md",
                "../ARCHITECTURE.md",
                "../CONTRACTS.md",
                "../MODELS.md",
            ),
            "USERS.md": ("../BUSINESS.md", "../MODELS.md"),
            "VDS.md": (
                "../ARCHITECTURE.md",
                "../CONTRACTS.md",
                "../MODELS.md",
            ),
            "VPN.md": (
                "../BUSINESS.md",
                "../CONTRACTS.md",
                "../MODELS.md",
            ),
        }
        for app_name, required_links in required_by_app.items():
            for missing_link in required_links:
                with self.subTest(app=app_name, missing=missing_link):
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        root = Path(tmp_dir)
                        docs = root / "docs"
                        apps = docs / "apps"
                        apps.mkdir(parents=True)
                        for target in {
                            link.removeprefix("../")
                            for links in required_by_app.values()
                            for link in links
                        }:
                            (docs / target).write_text(
                                f"# {target}\n",
                                encoding="utf-8",
                            )
                        links = [
                            f"[{target}]({target})"
                            for target in required_links
                            if target != missing_link
                        ]
                        (apps / app_name).write_text(
                            "# App\n\n## Зона ответственности\n\n"
                            + "\n".join(links)
                            + "\n",
                            encoding="utf-8",
                        )

                        result = self.run_checker(root)

                    self.assertEqual(result.returncode, 1)
                    self.assertIn(
                        f"app map must link to {missing_link}",
                        result.stdout,
                    )


if __name__ == "__main__":
    unittest.main()
