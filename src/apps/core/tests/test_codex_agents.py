from __future__ import annotations

import re
import subprocess
import sys
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
        definitions = [tomllib.loads(path.read_text(encoding="utf-8")) for path in paths]

        self.assertEqual(len(paths), len(expected_names))
        self.assertSetEqual({path.stem for path in paths}, expected_names)
        self.assertSetEqual({definition["name"] for definition in definitions}, expected_names)
        for definition in definitions:
            self.assertIsInstance(definition["description"], str)
            self.assertTrue(definition["description"].strip())
            self.assertIsInstance(definition["developer_instructions"], str)
            self.assertTrue(definition["developer_instructions"].strip())

    def test_role_instructions_preserve_their_key_boundaries(self) -> None:
        required_markers = {
            "product-agent": ("business.md", "BR-001", "AC-001", "не изменяй production-код"),
            "product-architect": ("без второго текущего", "ERD", "changes_requested"),
            "plan-maker": ("максимум из 10", "не более двух пунктов", "пересекающихся файлов"),
            "plan-implementer": ("RED → GREEN → REFACTOR", "больше двух", "commit, push или deploy"),
            "code-reviewer": (
                "режим batch",
                "pull_request",
                "gh pr review --comment",
                "headRefOid",
                "VERDICT: approved",
                "не изменяй файлы",
            ),
            "product-reviewer": (
                "acceptance.md",
                "Для каждого BR и AC",
                "реализующий код или контракт",
                "подтверждающий тест",
                "наблюдаемый результат",
                "passed, failed или unverified",
                "Не изменяй",
                "production-код",
            ),
        }

        for name, markers in required_markers.items():
            with self.subTest(name=name):
                path = self.agents_dir / f"{name}.toml"
                definition = tomllib.loads(path.read_text(encoding="utf-8"))
                instructions = definition["developer_instructions"]
                for marker in markers:
                    self.assertIn(marker, instructions)

    def test_every_role_uses_the_same_concise_packet_contract(self) -> None:
        packet_markers = (
            "mode",
            "scope_revision",
            "BR/AC IDs",
            "разрешённые файлы",
            "ссылки на артефакты",
            "зависимости",
            "non-goals",
            "бюджет",
            "критерий завершения",
        )
        forbidden_full_manifest_reads = (
            "Прочитай актуальный task.toml",
            "docs/DEVELOPMENT_WORKFLOW.md, task.toml",
            "актуальным task.toml",
        )

        for path in self.agents_dir.glob("*.toml"):
            with self.subTest(role=path.stem):
                instructions = tomllib.loads(path.read_text(encoding="utf-8"))[
                    "developer_instructions"
                ]
                for marker in packet_markers:
                    self.assertIn(marker, instructions)
                for forbidden in forbidden_full_manifest_reads:
                    self.assertNotIn(forbidden, instructions)

    def test_work_artifact_creators_require_exact_scope_revision(self) -> None:
        creator_roles = (
            "product-agent",
            "product-architect",
            "plan-maker",
            "product-reviewer",
        )

        for role in creator_roles:
            with self.subTest(role=role):
                instructions = tomllib.loads(
                    (self.agents_dir / f"{role}.toml").read_text(encoding="utf-8")
                )["developer_instructions"]
                self.assertIn(
                    "Запиши `scope_revision` из packet ровно один раз",
                    instructions,
                )

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

    def test_repository_instructions_route_to_adaptive_delivery_workflow(self) -> None:
        instructions = (self.repo_root / "AGENTS.md").read_text(encoding="utf-8")
        workflow = (self.repo_root / "docs" / "DEVELOPMENT_WORKFLOW.md").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "[DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md)",
            instructions,
        )
        self.assertNotIn("scope_revision", instructions)
        self.assertIn("## 2. Маршрут задачи", workflow)
        for role in (
            "product-agent",
            "product-architect",
            "plan-maker",
            "plan-implementer",
            "code-reviewer",
            "product-reviewer",
        ):
            with self.subTest(role=role):
                self.assertIn(role, workflow)
        self.assertIn("не более двух пунктов", workflow)
        self.assertIn("незавершённых зависимостей", workflow)
        self.assertIn("все write-сессии должны завершиться", workflow)
        self.assertIn("gh pr review --comment", workflow)
        self.assertIn("оставляет PR открытым", workflow)
        self.assertIn("`assigned IDs = []`", workflow)
        self.assertIn("`dependencies = []`", workflow)

        result = subprocess.run(
            (sys.executable, "scripts/check_docs_boundaries.py"),
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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

    def test_final_reviewer_uses_pr_review_brief_not_working_artifacts(self) -> None:
        path = self.agents_dir / "code-reviewer.toml"
        instructions = tomllib.loads(path.read_text(encoding="utf-8"))[
            "developer_instructions"
        ]

        self.assertIn("Review Brief", instructions)
        self.assertIn(".codex/work/", instructions)
        self.assertIn("не читай", instructions)

    def test_delivery_workflow_publishes_a_reviewed_pull_request(self) -> None:
        workflow = (self.repo_root / "docs" / "DEVELOPMENT_WORKFLOW.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("`codex/<feature-slug>`", workflow)
        self.assertIn("gh auth status", workflow)
        self.assertIn("gh pr create --base main", workflow)
        self.assertIn("gh pr checks", workflow)
        self.assertIn("gh pr review --comment", workflow)
        self.assertIn("--match-head-commit", workflow)
        self.assertIn("оставляет PR открытым", workflow)
        self.assertNotIn("git push origin main", workflow)

    def test_pull_request_template_contains_compact_review_brief(self) -> None:
        template = (
            self.repo_root / ".github" / "pull_request_template.md"
        ).read_text(encoding="utf-8")

        for heading in (
            "## Review Brief",
            "### Goal",
            "### Observable behavior",
            "### Non-goals",
            "### Acceptance criteria",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, template)

    def test_github_runs_tests_for_pull_requests_to_main(self) -> None:
        workflow = (self.repo_root / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("pull_request:", workflow)
        self.assertIn("branches: [main]", workflow)
        self.assertIn("uv run make test", workflow)

    def test_repository_instructions_reference_current_telegram_and_music_paths(
        self,
    ) -> None:
        instructions = (self.repo_root / "AGENTS.md").read_text(encoding="utf-8")
        core_docs = (self.repo_root / "docs" / "apps" / "CORE.md").read_text(
            encoding="utf-8"
        )
        role_instructions = "\n".join(
            tomllib.loads(path.read_text(encoding="utf-8"))["developer_instructions"]
            for path in self.agents_dir.glob("*.toml")
        )

        self.assertNotIn("apps.core.bot.TelegramBot", instructions)
        self.assertIn("apps.core.telegram.transport", instructions)
        self.assertIn("`src/apps/music/`", instructions)
        self.assertTrue((self.repo_root / "src" / "apps" / "music").is_dir())
        self.assertNotIn("не изменяй apps/music", role_instructions)
        self.assertNotIn("Не изучай\napps/music", role_instructions)
        self.assertIn("src/apps/music/", role_instructions)
        self.assertIn("**dtos.py**", core_docs)

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

    def test_deploy_guide_requires_fresh_permission_before_deploy_playbook(self) -> None:
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
