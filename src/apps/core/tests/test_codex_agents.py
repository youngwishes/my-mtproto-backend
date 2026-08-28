from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

from django.test import SimpleTestCase


class TestCodexAgents(SimpleTestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[4]
        self.agents_dir = self.repo_root / ".codex" / "agents"

    def test_project_defines_the_product_delivery_roles(self) -> None:
        expected_names = {
            "product-agent",
            "product-architect",
            "plan-maker",
            "plan-implementer",
            "code-reviewer",
            "product-reviewer",
        }

        paths = sorted(self.agents_dir.glob("*.toml"))
        definitions = [
            tomllib.loads(path.read_text(encoding="utf-8")) for path in paths
        ]

        self.assertEqual(len(paths), len(expected_names))
        self.assertSetEqual({path.stem for path in paths}, expected_names)
        self.assertSetEqual(
            {definition["name"] for definition in definitions}, expected_names
        )
        for definition in definitions:
            self.assertIsInstance(definition["description"], str)
            self.assertTrue(definition["description"].strip())
            self.assertIsInstance(definition["developer_instructions"], str)
            self.assertTrue(definition["developer_instructions"].strip())

    def test_code_reviewer_requests_a_read_only_default(self) -> None:
        path = self.agents_dir / "code-reviewer.toml"

        definition = tomllib.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(definition["sandbox_mode"], "read-only")

    def test_orchestrator_limits_parallelism_and_spawn_depth(self) -> None:
        path = self.repo_root / ".codex" / "config.toml"

        config = tomllib.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(config.get("approval_policy"), "never")
        self.assertEqual(config.get("sandbox_mode"), "danger-full-access")
        self.assertEqual(config["agents"]["max_threads"], 6)
        self.assertEqual(config["agents"]["max_depth"], 1)

    def test_agent_working_artifacts_are_ignored_and_untracked(self) -> None:
        ignored_examples = (
            ".codex/work/example-feature/business.md",
            "docs/features/legacy-feature/plan.md",
            "docs/superpowers/specs/legacy-design.md",
            "superpowers/specs/legacy-design.md",
        )

        for relative_path in ignored_examples:
            with self.subTest(relative_path=relative_path):
                result = subprocess.run(
                    ("git", "check-ignore", "--quiet", "--no-index", relative_path),
                    cwd=self.repo_root,
                    check=False,
                )
                self.assertEqual(result.returncode, 0)

        tracked = subprocess.run(
            (
                "git",
                "ls-files",
                "--",
                "docs/features",
                "docs/superpowers",
                "superpowers",
            ),
            cwd=self.repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(tracked.stdout, "")

    def test_api_contract_endpoint_headings_use_absolute_v1_paths(self) -> None:
        contracts = (self.repo_root / "docs" / "CONTRACTS.md").read_text(
            encoding="utf-8"
        )
        endpoint_paths = re.findall(
            r"^### (?:GET|POST|PATCH|DELETE) (\S+)", contracts, re.MULTILINE
        )

        self.assertTrue(endpoint_paths)
        self.assertTrue(
            all(path.startswith("/api/v1/") for path in endpoint_paths),
            endpoint_paths,
        )

    def test_product_price_unit_is_consistent_in_canonical_docs(self) -> None:
        models = (self.repo_root / "docs" / "MODELS.md").read_text(encoding="utf-8")
        contracts = (self.repo_root / "docs" / "CONTRACTS.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Цена в копейках", models)
        self.assertIn("`price` хранится и возвращается в копейках", contracts)

    def test_deploy_guide_requires_fresh_permission_before_deploy_playbook(
        self,
    ) -> None:
        deploy = (self.repo_root / "docs" / "DEPLOY.md").read_text(encoding="utf-8")
        release_section = deploy.split("## Новый релиз", maxsplit=1)[1].split(
            "## Crypto Pay rollout", maxsplit=1
        )[0]

        permission_text = (
            "новое явное разрешение пользователя непосредственно\n   перед deploy"
        )
        self.assertIn(permission_text, release_section)
        permission_gate = release_section.index(permission_text)
        deploy_playbook = release_section.index(
            'ansible-playbook -i ansible/inventory/production.ini ansible/deploy.yml \\\n     -e deploy_revision="$RELEASE_SHA"'
        )
        self.assertLess(permission_gate, deploy_playbook)

    def test_architecture_lists_every_production_compose_service(self) -> None:
        compose = (self.repo_root / "docker-compose.yml").read_text(encoding="utf-8")
        architecture = (self.repo_root / "docs" / "ARCHITECTURE.md").read_text(
            encoding="utf-8"
        )
        services_block = compose.split("services:\n", maxsplit=1)[1].split(
            "\nvolumes:", maxsplit=1
        )[0]
        compose_services = {
            line.strip().removesuffix(":")
            for line in services_block.splitlines()
            if line.startswith("  ")
            and not line.startswith("    ")
            and line.endswith(":")
        }
        documented_services = {
            match.group(1)
            for match in re.finditer(
                r"^\| ([a-z][a-z0-9-]+) \|", architecture, re.MULTILINE
            )
        }

        self.assertSetEqual(documented_services, compose_services)
