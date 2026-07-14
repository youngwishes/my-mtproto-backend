from __future__ import annotations

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
            "code-reviewer": ("режим batch", "integration", "не изменяй файлы"),
            "product-reviewer": (
                "acceptance.md",
                "Для каждого BR и AC",
                "реализующий код или контракт",
                "подтверждающий тест",
                "наблюдаемый результат",
                "passed, failed или unverified",
                "Не изменяй production-код",
            ),
        }

        for name, markers in required_markers.items():
            with self.subTest(name=name):
                path = self.agents_dir / f"{name}.toml"
                definition = tomllib.loads(path.read_text(encoding="utf-8"))
                instructions = definition["developer_instructions"]
                for marker in markers:
                    self.assertIn(marker, instructions)

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

    def test_repository_instructions_define_adaptive_agent_routing(self) -> None:
        instructions = (self.repo_root / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("## Адаптивная продуктовая команда", instructions)
        short_route = instructions.split("- небольшая локальная фича:", maxsplit=1)[1].split(
            ";", maxsplit=1
        )[0]
        self.assertIn("plan-maker", short_route)
        self.assertIn("не более двух пунктов плана", instructions)
        self.assertIn("без незавершённых зависимостей", instructions)
        self.assertIn("отдельный `code-reviewer`", instructions)
        self.assertIn("новый экземпляр `code-reviewer`", instructions)
        self.assertIn("интеграционное ревью", instructions)
        self.assertIn("runtime permissions", instructions)
        self.assertIn("не запускает reviewer параллельно с write-сессиями", instructions)
        self.assertIn("git status", instructions)
