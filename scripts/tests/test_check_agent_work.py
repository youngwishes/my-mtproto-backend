from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class TestCheckAgentWork(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.checker = self.repo_root / "scripts" / "check_agent_work.py"

    def write_work(
        self,
        root: Path,
        *,
        feature_slug: str = "test-feature",
        status: str = "implementing",
        include_batch: bool = True,
    ) -> Path:
        work_dir = root / feature_slug
        work_dir.mkdir()
        requirement_ids = '[]' if status == "draft" else '["BR-001", "AC-001"]'
        manifest_text = textwrap.dedent(
            f"""
            feature_slug = "{feature_slug}"
            scope_revision = 1
            status = "{status}"
            requirements_source = "scope.md"
            requirement_ids = {requirement_ids}
            allowed_files = ["src/service.py", "src/test_service.py"]
            non_goals = ["No unrelated changes"]
            done_when = "Focused and repository checks pass"
            """
        ).strip()
        if include_batch:
            manifest_text += "\n\n" + textwrap.dedent(
                """
                [[batches]]
                id = "B1"
                items = ["EX-001"]
                requirements = ["BR-001", "AC-001"]
                allowed_files = ["src/service.py", "src/test_service.py"]
                dependencies = []
                """
            ).strip()
        (work_dir / "task.toml").write_text(
            manifest_text + "\n", encoding="utf-8"
        )
        return work_dir

    def run_checker(
        self,
        *,
        work_dir: Path | None = None,
        repo_root: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command: list[str | Path] = [sys.executable, self.checker]
        if work_dir is not None:
            command.extend(("--work-dir", work_dir))
        if repo_root is not None:
            command.extend(("--repo-root", repo_root))
        return subprocess.run(
            command,
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            text=True,
        )

    def initialize_git_repo(self, repo_root: Path) -> None:
        subprocess.run(
            ("git", "init", "-b", "codex/test-feature"),
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        (repo_root / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(("git", "add", "README.md"), cwd=repo_root, check=True)
        subprocess.run(
            (
                "git",
                "-c",
                "user.name=Codex Tests",
                "-c",
                "user.email=codex-tests@example.invalid",
                "commit",
                "-m",
                "fixture",
            ),
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        subprocess.run(("git", "branch", "main"), cwd=repo_root, check=True)

    def test_valid_minimal_manifest_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_work(Path(tmp_dir))
            result = self.run_checker(work_dir=work_dir)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Agent work contract: OK", result.stdout)

    def test_draft_can_precede_requirements_and_batches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_work(
                Path(tmp_dir),
                status="draft",
                include_batch=False,
            )
            result = self.run_checker(work_dir=work_dir)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_example_manifest_is_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir) / "example-feature"
            work_dir.mkdir()
            (work_dir / "task.toml").write_text(
                (self.repo_root / ".codex" / "task.example.toml").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir=work_dir)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_malformed_toml_has_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir) / "test-feature"
            work_dir.mkdir()
            (work_dir / "task.toml").write_text(
                'feature_slug = "unterminated\n',
                encoding="utf-8",
            )
            result = self.run_checker(work_dir=work_dir)

        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid TOML", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_required_task_fields_are_enforced(self) -> None:
        fields = (
            "feature_slug",
            "requirements_source",
            "allowed_files",
            "non_goals",
            "done_when",
        )
        for field in fields:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp_dir:
                work_dir = self.write_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                lines = manifest.read_text(encoding="utf-8").splitlines()
                manifest.write_text(
                    "\n".join(line for line in lines if not line.startswith(f"{field} ="))
                    + "\n",
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir=work_dir)

                self.assertEqual(result.returncode, 1)
                self.assertIn(field, result.stdout)

    def test_unknown_manifest_fields_are_rejected(self) -> None:
        cases = (
            ("feature_slug =", "legacy = true\nfeature_slug =", "unknown task fields"),
            ("dependencies = []", "dependencies = []\nlegacy = true", "unknown fields"),
        )
        for old, new, expected in cases:
            with (
                self.subTest(expected=expected),
                tempfile.TemporaryDirectory() as tmp_dir,
            ):
                work_dir = self.write_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(old, new, 1),
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir=work_dir)

                self.assertEqual(result.returncode, 1)
                self.assertIn(expected, result.stdout)

    def test_status_and_revision_are_validated(self) -> None:
        cases = (
            ('status = "implementing"', 'status = "unknown"', "status"),
            ("scope_revision = 1", "scope_revision = true", "scope_revision"),
            ("scope_revision = 1", "scope_revision = 0", "scope_revision"),
        )
        for old, new, expected in cases:
            with self.subTest(new=new), tempfile.TemporaryDirectory() as tmp_dir:
                work_dir = self.write_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(old, new),
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir=work_dir)

                self.assertEqual(result.returncode, 1)
                self.assertIn(expected, result.stdout)

    def test_requirement_ids_use_stable_unique_format(self) -> None:
        cases = (
            '["BR-1", "AC-001"]',
            '["BR-001", "BR-001", "AC-001"]',
        )
        for ids in cases:
            with self.subTest(ids=ids), tempfile.TemporaryDirectory() as tmp_dir:
                work_dir = self.write_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(
                        '["BR-001", "AC-001"]',
                        ids,
                        1,
                    ),
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir=work_dir)

                self.assertEqual(result.returncode, 1)
                self.assertIn("requirement_ids", result.stdout)

    def test_implementation_requires_a_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_work(Path(tmp_dir), include_batch=False)
            result = self.run_checker(work_dir=work_dir)

        self.assertEqual(result.returncode, 1)
        self.assertIn("requires at least one batch", result.stdout)

    def test_batch_contains_at_most_two_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'items = ["EX-001"]',
                    'items = ["EX-001", "EX-002", "EX-003"]',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir=work_dir)

        self.assertEqual(result.returncode, 1)
        self.assertIn("maximum is 2", result.stdout)

    def test_batch_requires_a_complete_small_packet(self) -> None:
        fields = ("id", "items", "requirements", "allowed_files", "dependencies")
        for field in fields:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp_dir:
                work_dir = self.write_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                lines = manifest.read_text(encoding="utf-8").splitlines()
                in_batch = False
                filtered_lines = []
                for line in lines:
                    if line == "[[batches]]":
                        in_batch = True
                    if line.startswith(f"{field} =") and (
                        field != "allowed_files" or in_batch
                    ):
                        continue
                    filtered_lines.append(line)
                manifest.write_text(
                    "\n".join(filtered_lines) + "\n",
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir=work_dir)

                self.assertEqual(result.returncode, 1)
                if field == "allowed_files":
                    self.assertIn("batch B1 is missing allowed_files", result.stdout)
                else:
                    self.assertIn(field, result.stdout)

    def test_batch_scope_is_a_subset_of_task_scope(self) -> None:
        cases = (
            (
                'requirements = ["BR-001", "AC-001"]',
                'requirements = ["BR-001", "AC-001", "BR-999"]',
                "BR-999",
            ),
            (
                'allowed_files = ["src/service.py", "src/test_service.py"]',
                'allowed_files = ["src/service.py", "src/other.py"]',
                "src/other.py",
            ),
        )
        for old, new, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp_dir:
                work_dir = self.write_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                text = manifest.read_text(encoding="utf-8")
                if "other" in new:
                    prefix, separator, suffix = text.rpartition(old)
                    text = prefix + new + suffix if separator else text
                else:
                    text = text.replace(old, new, 1)
                manifest.write_text(text, encoding="utf-8")
                result = self.run_checker(work_dir=work_dir)

                self.assertEqual(result.returncode, 1)
                self.assertIn(expected, result.stdout)

    def test_batch_dependencies_reference_declared_batches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    "dependencies = []",
                    'dependencies = ["UNKNOWN"]',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir=work_dir)

        self.assertEqual(result.returncode, 1)
        self.assertIn("UNKNOWN", result.stdout)

    def test_feature_slug_matches_work_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'feature_slug = "test-feature"',
                    'feature_slug = "different"',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir=work_dir)

        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match work directory", result.stdout)

    def test_cli_resolves_work_from_codex_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            repo_root.mkdir()
            self.initialize_git_repo(repo_root)
            work_parent = repo_root / ".codex" / "work"
            work_parent.mkdir(parents=True)
            self.write_work(work_parent)
            result = self.run_checker(repo_root=repo_root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cli_rejects_non_codex_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            repo_root.mkdir()
            self.initialize_git_repo(repo_root)
            subprocess.run(("git", "switch", "main"), cwd=repo_root, check=True, capture_output=True)
            result = self.run_checker(repo_root=repo_root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("codex/<feature-slug>", result.stdout)

    def test_cli_rejects_nested_feature_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            repo_root.mkdir()
            self.initialize_git_repo(repo_root)
            subprocess.run(
                ("git", "branch", "-m", "codex/team/test-feature"),
                cwd=repo_root,
                check=True,
            )
            work_parent = repo_root / ".codex" / "work" / "team"
            work_parent.mkdir(parents=True)
            self.write_work(work_parent)
            result = self.run_checker(repo_root=repo_root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("feature slug must not contain '/'", result.stdout)

    def test_cli_rejects_changed_files_outside_task_scope(self) -> None:
        for committed in (False, True):
            with self.subTest(committed=committed), tempfile.TemporaryDirectory() as tmp_dir:
                repo_root = Path(tmp_dir) / "repo"
                repo_root.mkdir()
                self.initialize_git_repo(repo_root)
                work_parent = repo_root / ".codex" / "work"
                work_parent.mkdir(parents=True)
                self.write_work(work_parent)
                outside = repo_root / "src" / "outside.py"
                outside.parent.mkdir()
                outside.write_text("outside = True\n", encoding="utf-8")
                if committed:
                    subprocess.run(("git", "add", "src/outside.py"), cwd=repo_root, check=True)
                    subprocess.run(
                        (
                            "git",
                            "-c",
                            "user.name=Codex Tests",
                            "-c",
                            "user.email=codex-tests@example.invalid",
                            "commit",
                            "-m",
                            "outside",
                        ),
                        cwd=repo_root,
                        check=True,
                        capture_output=True,
                    )
                result = self.run_checker(repo_root=repo_root)

                self.assertEqual(result.returncode, 1)
                self.assertIn("src/outside.py", result.stdout)


if __name__ == "__main__":
    unittest.main()
