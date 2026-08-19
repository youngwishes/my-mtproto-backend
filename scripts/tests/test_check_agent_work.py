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

    def write_valid_work(
        self,
        root: Path,
        *,
        artifact_revision: int = 1,
        scope_revision: int = 1,
        previous_scope_revision: int | None = None,
        previous_status: str = "approved",
        status: str = "implementing",
        blocking_reference: str | None = None,
    ) -> Path:
        work_dir = root / "test-feature"
        work_dir.mkdir()
        (work_dir / "scope.md").write_text(
            f"# Scope\n\n- `scope_revision`: {artifact_revision}\n"
            "- BR-001: Required behavior.\n"
            "- AC-001: Observable acceptance.\n",
            encoding="utf-8",
        )
        previous_revision_line = (
            f"previous_scope_revision = {previous_scope_revision}\n"
            if previous_scope_revision is not None
            else ""
        )
        blocking_reference_line = (
            f'blocking_reference = "{blocking_reference}"\n'
            if blocking_reference is not None
            else ""
        )
        (work_dir / "task.toml").write_text(
            textwrap.dedent(
                f"""
                schema_version = 1
                feature_slug = "test-feature"
                scope_revision = {scope_revision}
                {previous_revision_line.rstrip()}
                previous_status = "{previous_status}"
                status = "{status}"
                requirements_source = "scope.md"
                requirement_ids = ["BR-001", "AC-001"]
                allowed_files = ["scripts/check_agent_work.py"]
                non_goals = ["No unrelated behavior"]
                budget = "One bounded task"
                completion = "Approved outcome is verified"
                max_artifact_lines = 300
                max_total_artifact_lines = 600
                {blocking_reference_line.rstrip()}

                [artifacts]
                scope = "scope.md"

                [[batches]]
                id = "B1"
                items = ["AW-001"]
                requirements = ["BR-001", "AC-001"]
                allowed_files = ["scripts/check_agent_work.py"]
                dependencies = []
                non_goals = ["No runtime behavior changes"]
                budget = "One checker"
                completion = "Focused tests pass"
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        return work_dir

    def run_checker(self, work_dir: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (sys.executable, self.checker, "--work-dir", work_dir),
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
            text=True,
        )
        (repo_root / "README.md").write_text("fixture\n", encoding="utf-8")
        outside_file = repo_root / "src" / "outside.py"
        outside_file.parent.mkdir()
        outside_file.write_text("outside = True\n", encoding="utf-8")
        subprocess.run(
            ("git", "add", "README.md", "src/outside.py"),
            cwd=repo_root,
            check=True,
        )
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
            text=True,
        )
        subprocess.run(("git", "branch", "main"), cwd=repo_root, check=True)

    def test_valid_active_task_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Agent work contract: OK", result.stdout)

    def test_initial_product_draft_can_precede_requirements_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir) / "new-product-feature"
            work_dir.mkdir()
            (work_dir / "task.toml").write_text(
                textwrap.dedent(
                    """
                    schema_version = 1
                    feature_slug = "new-product-feature"
                    scope_revision = 1
                    status = "draft"
                    requirements_source = "business.md"
                    requirement_ids = []
                    allowed_files = ["business.md"]
                    non_goals = ["No architecture or implementation"]
                    budget = "One product requirements artifact"
                    completion = "Requirements are explicitly approved"
                    max_artifact_lines = 300
                    max_total_artifact_lines = 600

                    [artifacts]
                    business = "business.md"
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Agent work contract: OK", result.stdout)

    def test_approved_preplan_task_can_precede_batches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(
                Path(tmp_dir),
                previous_status="draft",
                status="approved",
            )
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").split(
                    "[[batches]]",
                    maxsplit=1,
                )[0],
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Agent work contract: OK", result.stdout)

    def test_repository_example_manifest_is_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir) / "example-feature"
            work_dir.mkdir()
            (work_dir / "task.toml").write_text(
                (self.repo_root / ".codex" / "task.example.toml").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            (work_dir / "scope.md").write_text(
                "# Example scope\n\n- `scope_revision`: 1\n"
                "- BR-001: Required behavior.\n"
                "- AC-001: Observable acceptance.\n",
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Agent work contract: OK", result.stdout)

    def test_artifact_revision_must_match_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir), artifact_revision=2)
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("scope.md", result.stdout)
        self.assertIn("scope_revision 2 does not match task.toml revision 1", result.stdout)

    def test_declared_artifact_must_state_scope_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            (work_dir / "scope.md").write_text("# Scope without revision\n", encoding="utf-8")
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("scope.md: declared artifact must state scope_revision", result.stdout)

    def test_declared_artifact_must_have_one_scope_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            scope = work_dir / "scope.md"
            scope.write_text(
                scope.read_text(encoding="utf-8") + "- `scope_revision`: 2\n",
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("declared artifact must state scope_revision exactly once", result.stdout)

    def test_artifact_scope_revision_requires_exact_positive_integer(self) -> None:
        for malformed_value in ("-1", "1.5", "1foo"):
            with (
                self.subTest(value=malformed_value),
                tempfile.TemporaryDirectory() as tmp_dir,
            ):
                work_dir = self.write_valid_work(Path(tmp_dir))
                scope = work_dir / "scope.md"
                scope.write_text(
                    scope.read_text(encoding="utf-8").replace(
                        "`scope_revision`: 1",
                        f"`scope_revision`: {malformed_value}",
                    ),
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir)

                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(
                    "scope_revision must be one positive integer",
                    result.stdout,
                )

    def test_invalid_status_transition_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(
                Path(tmp_dir),
                previous_status="draft",
                status="implementing",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("invalid status transition: draft -> implementing", result.stdout)

    def test_retained_scope_revision_files_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            (work_dir / "scope-r2.md").write_text(
                "# Historical scope\n\n- `scope_revision`: 2\n",
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("scope-r2.md", result.stdout)
        self.assertIn("retained scope revision is forbidden", result.stdout)

    def test_raw_diff_artifacts_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            (work_dir / "product-review.diff").write_text(
                "diff --git a/example b/example\n",
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("product-review.diff", result.stdout)
        self.assertIn("raw diff/patch artifacts are forbidden", result.stdout)

    def test_raw_diff_detection_ignores_name_and_extension_case(self) -> None:
        for relative_path in ("review.DIFF", "review.txt"):
            with (
                self.subTest(path=relative_path),
                tempfile.TemporaryDirectory() as tmp_dir,
            ):
                work_dir = self.write_valid_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(
                        'scope = "scope.md"',
                        f'scope = "scope.md"\nreview = "{relative_path}"',
                    ),
                    encoding="utf-8",
                )
                (work_dir / relative_path).write_text(
                    "- `scope_revision`: 1\ndiff --git a/example b/example\n",
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir)

                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("raw diff/patch artifacts are forbidden", result.stdout)

    def test_undeclared_work_artifacts_cannot_bypass_history_or_size_gates(self) -> None:
        cases = (
            ("history/scope-r2.md", "historical revision\n"),
            ("business-r1.md", "historical requirements\n"),
            ("review.patch", "diff --git a/example b/example\n"),
            ("plan.md", "step\n" * 301),
        )
        for relative_path, content in cases:
            with self.subTest(path=relative_path), tempfile.TemporaryDirectory() as tmp_dir:
                work_dir = self.write_valid_work(Path(tmp_dir))
                artifact = work_dir / relative_path
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_text(content, encoding="utf-8")
                result = self.run_checker(work_dir)

                self.assertEqual(
                    result.returncode,
                    1,
                    result.stdout + result.stderr,
                )
                self.assertIn(
                    f"undeclared work artifact: {relative_path}",
                    result.stdout,
                )

    def test_declared_artifact_over_line_budget_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'scope = "scope.md"',
                    'scope = "scope.md"\nplan = "plan.md"',
                ),
                encoding="utf-8",
            )
            (work_dir / "plan.md").write_text(
                "# Plan\n\n- `scope_revision`: 1\n" + "step\n" * 298,
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("plan.md", result.stdout)
        self.assertIn("301 lines exceeds max_artifact_lines 300", result.stdout)

    def test_manifest_cannot_bypass_content_or_line_budgets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'budget = "One bounded task"',
                    'budget = """One bounded task\ndiff --git a/example b/example"""',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("task.toml: raw diff/patch content is forbidden", result.stdout)

        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    "max_artifact_lines = 300",
                    "max_artifact_lines = 20",
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("task.toml", result.stdout)
        self.assertIn("exceeds max_artifact_lines 20", result.stdout)

        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'budget = "One bounded task"',
                    'budget = """One bounded task\nBR-001: copied text"""',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "requirement definitions are allowed only in requirements_source",
            result.stdout,
        )

    def test_batch_with_more_than_two_items_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'items = ["AW-001"]',
                    'items = ["AW-001", "AW-002", "AW-003"]',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("batch B1 assigns 3 items; maximum is 2", result.stdout)

    def test_requirements_source_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'requirements_source = "scope.md"\n',
                    "",
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("requirements_source must be a non-empty string", result.stdout)

    def test_feature_slug_must_match_work_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'feature_slug = "test-feature"',
                    'feature_slug = "different-feature"',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "feature_slug different-feature does not match work directory test-feature",
            result.stdout,
        )

    def test_batch_cannot_expand_manifest_file_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'allowed_files = ["scripts/check_agent_work.py"]\n'
                    'dependencies = []',
                    'allowed_files = ["scripts/check_agent_work.py", "src/runtime.py"]\n'
                    'dependencies = []',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("batch B1 contains files outside task ownership: src/runtime.py", result.stdout)

    def test_batch_cannot_introduce_unapproved_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'requirements = ["BR-001", "AC-001"]',
                    'requirements = ["BR-001", "AC-001", "BR-999"]',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("batch B1 contains unapproved requirements: BR-999", result.stdout)

    def test_task_requirement_ids_must_match_requirements_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8")
                .replace(
                    'requirement_ids = ["BR-001", "AC-001"]',
                    'requirement_ids = ["BR-001", "AC-001", "BR-999"]',
                )
                .replace(
                    'requirements = ["BR-001", "AC-001"]',
                    'requirements = ["BR-001", "AC-001", "BR-999"]',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("requirement_ids not declared in scope.md: BR-999", result.stdout)

    def test_task_requirement_ids_require_stable_format_and_uniqueness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'requirement_ids = ["BR-001", "AC-001"]',
                    'requirement_ids = ["BR-1", "AC-001"]',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("invalid requirement_ids: BR-1", result.stdout)

        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'requirement_ids = ["BR-001", "AC-001"]',
                    'requirement_ids = ["BR-001", "BR-001", "AC-001"]',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("duplicate requirement_ids: BR-001", result.stdout)

    def test_batch_packet_requires_all_handoff_fields(self) -> None:
        cases = (
            ("dependencies = []\n", "dependencies", "missing dependencies"),
            (
                'non_goals = ["No runtime behavior changes"]\n',
                "non_goals",
                "missing non-empty non_goals",
            ),
            ('budget = "One checker"\n', "budget", "missing non-empty budget"),
            (
                'completion = "Focused tests pass"\n',
                "completion",
                "missing non-empty completion",
            ),
        )
        for manifest_line, field, expected in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp_dir:
                work_dir = self.write_valid_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(manifest_line, ""),
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir)

                self.assertEqual(
                    result.returncode,
                    1,
                    result.stdout + result.stderr,
                )
                self.assertIn(
                    f"batch B1 is {expected}",
                    result.stdout,
                )

    def test_published_task_requires_exact_reviewed_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(
                Path(tmp_dir),
                previous_status="accepted",
                status="published",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("published task requires a 40-character reviewed_sha", result.stdout)

    def test_reviewed_sha_is_forbidden_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'status = "implementing"\n',
                    f'status = "implementing"\nreviewed_sha = "{"0" * 40}"\n',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("reviewed_sha is allowed only for published status", result.stdout)

    def test_published_reviewed_sha_must_match_expected_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(
                Path(tmp_dir),
                previous_status="accepted",
                status="published",
            )
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'status = "published"\n',
                    f'status = "published"\nreviewed_sha = "{"0" * 40}"\n',
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                (
                    sys.executable,
                    self.checker,
                    "--work-dir",
                    work_dir,
                    "--expected-head-sha",
                    "1" * 40,
                ),
                cwd=self.repo_root,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("reviewed_sha does not match expected head SHA", result.stdout)

    def test_closed_task_directory_must_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(
                Path(tmp_dir),
                previous_status="published",
                status="closed",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("closed task directory must be removed", result.stdout)

    def test_malformed_manifest_reports_actionable_error_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir) / "test-feature"
            work_dir.mkdir()
            (work_dir / "task.toml").write_text(
                'feature_slug = "unterminated\n',
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("task.toml: invalid TOML", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_lifecycle_fields_reject_non_string_types_without_traceback(self) -> None:
        cases = (
            ('status = "implementing"', 'status = ["implementing"]', "status must be"),
            (
                'previous_status = "approved"',
                'previous_status = ["approved"]',
                "previous_status must be a string",
            ),
        )
        for old, new, expected in cases:
            with self.subTest(field=old), tempfile.TemporaryDirectory() as tmp_dir:
                work_dir = self.write_valid_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(old, new),
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir)

                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(expected, result.stdout)
                self.assertNotIn("Traceback", result.stderr)

    def test_previous_scope_revision_requires_strict_integer(self) -> None:
        for malformed_value in ("true", '"1"'):
            with (
                self.subTest(value=malformed_value),
                tempfile.TemporaryDirectory() as tmp_dir,
            ):
                work_dir = self.write_valid_work(
                    Path(tmp_dir),
                    artifact_revision=2,
                    scope_revision=2,
                    previous_scope_revision=1,
                    previous_status="implementing",
                    status="approved",
                )
                manifest = work_dir / "task.toml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(
                        "previous_scope_revision = 1",
                        f"previous_scope_revision = {malformed_value}",
                    ),
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir)

                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(
                    "previous_scope_revision must be a positive integer",
                    result.stdout,
                )

    def test_missing_artifact_budget_reports_schema_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    "max_artifact_lines = 300\n",
                    "",
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("max_artifact_lines must be a positive integer", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_manifest_schema_rejects_invalid_task_and_batch_shapes(self) -> None:
        cases = (
            (
                lambda text: text.replace("schema_version = 1", "schema_version = 2"),
                "schema_version must be 1",
            ),
            (
                lambda text: text.split("[[batches]]", maxsplit=1)[0],
                "implementation lifecycle requires at least one batch",
            ),
            (
                lambda text: text.replace("[[batches]]", "[batches]"),
                "batches must be an array of tables",
            ),
            (
                lambda text: text.replace('id = "B1"\n', ""),
                "batch 1 is missing non-empty id",
            ),
            (
                lambda text: text.replace('items = ["AW-001"]\n', ""),
                "batch B1 is missing non-empty items",
            ),
            (
                lambda text: text.replace(
                    'requirements = ["BR-001", "AC-001"]\n',
                    "",
                ),
                "batch B1 is missing non-empty requirements",
            ),
            (
                lambda text: text.replace(
                    'allowed_files = ["scripts/check_agent_work.py"]\n'
                    'dependencies = []',
                    "dependencies = []",
                ),
                "batch B1 is missing non-empty allowed_files",
            ),
        )
        for mutate, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp_dir:
                work_dir = self.write_valid_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                manifest.write_text(
                    mutate(manifest.read_text(encoding="utf-8")),
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir)

                self.assertEqual(
                    result.returncode,
                    1,
                    result.stdout + result.stderr,
                )
                self.assertIn(expected, result.stdout)
                self.assertNotIn("Traceback", result.stderr)

    def test_task_level_packet_requires_context_before_batches_exist(self) -> None:
        cases = (
            ('non_goals = ["No unrelated behavior"]\n', "non_goals"),
            ('budget = "One bounded task"\n', "budget"),
            ('completion = "Approved outcome is verified"\n', "completion"),
        )
        for manifest_line, field in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp_dir:
                work_dir = self.write_valid_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(manifest_line, ""),
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir)

                self.assertEqual(
                    result.returncode,
                    1,
                    result.stdout + result.stderr,
                )
                self.assertIn(
                    f"task packet is missing non-empty {field}",
                    result.stdout,
                )

    def test_manifest_schema_rejects_duplicate_batch_and_item_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            text = manifest.read_text(encoding="utf-8")
            batch = "[[batches]]" + text.split("[[batches]]", maxsplit=1)[1]
            manifest.write_text(text + "\n" + batch, encoding="utf-8")
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("duplicate batch ids: B1", result.stdout)

        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'items = ["AW-001"]',
                    'items = ["AW-001", "AW-001"]',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("duplicate item ids: AW-001", result.stdout)

    def test_cli_resolves_active_work_from_codex_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            repo_root.mkdir()
            self.initialize_git_repo(repo_root)
            work_parent = repo_root / ".codex" / "work"
            work_parent.mkdir(parents=True)
            self.write_valid_work(work_parent)

            result = subprocess.run(
                (sys.executable, self.checker, "--repo-root", repo_root),
                cwd=self.repo_root,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Agent work contract: OK", result.stdout)

    def test_cli_rejects_changed_repo_file_outside_task_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            repo_root.mkdir()
            self.initialize_git_repo(repo_root)
            work_parent = repo_root / ".codex" / "work"
            work_parent.mkdir(parents=True)
            self.write_valid_work(work_parent)
            runtime_file = repo_root / "src" / "runtime.py"
            runtime_file.parent.mkdir(exist_ok=True)
            runtime_file.write_text("changed = True\n", encoding="utf-8")

            result = subprocess.run(
                (sys.executable, self.checker, "--repo-root", repo_root),
                cwd=self.repo_root,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("changed files outside task ownership: src/runtime.py", result.stdout)

    def test_cli_rejects_committed_file_outside_task_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            repo_root.mkdir()
            self.initialize_git_repo(repo_root)
            work_parent = repo_root / ".codex" / "work"
            work_parent.mkdir(parents=True)
            self.write_valid_work(work_parent)
            runtime_file = repo_root / "src" / "runtime.py"
            runtime_file.parent.mkdir(exist_ok=True)
            runtime_file.write_text("changed = True\n", encoding="utf-8")
            subprocess.run(("git", "add", "src/runtime.py"), cwd=repo_root, check=True)
            subprocess.run(
                (
                    "git",
                    "-c",
                    "user.name=Codex Tests",
                    "-c",
                    "user.email=codex-tests@example.invalid",
                    "commit",
                    "-m",
                    "out of scope",
                ),
                cwd=repo_root,
                check=True,
                capture_output=True,
            )

            result = subprocess.run(
                (sys.executable, self.checker, "--repo-root", repo_root),
                cwd=self.repo_root,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("changed files outside task ownership: src/runtime.py", result.stdout)

    def test_cli_checks_both_paths_of_committed_rename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            repo_root.mkdir()
            self.initialize_git_repo(repo_root)
            work_parent = repo_root / ".codex" / "work"
            work_parent.mkdir(parents=True)
            self.write_valid_work(work_parent)
            destination = repo_root / "scripts" / "check_agent_work.py"
            destination.parent.mkdir()
            subprocess.run(
                ("git", "mv", "src/outside.py", "scripts/check_agent_work.py"),
                cwd=repo_root,
                check=True,
            )
            subprocess.run(
                (
                    "git",
                    "-c",
                    "user.name=Codex Tests",
                    "-c",
                    "user.email=codex-tests@example.invalid",
                    "commit",
                    "-m",
                    "rename outside ownership",
                ),
                cwd=repo_root,
                check=True,
                capture_output=True,
            )

            result = subprocess.run(
                (sys.executable, self.checker, "--repo-root", repo_root),
                cwd=self.repo_root,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("changed files outside task ownership: src/outside.py", result.stdout)

    def test_approved_scope_revision_can_restart_implementation_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(
                Path(tmp_dir),
                artifact_revision=2,
                scope_revision=2,
                previous_scope_revision=1,
                previous_status="implementing",
                status="approved",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Agent work contract: OK", result.stdout)

    def test_scope_revision_lineage_is_persistent_and_sequential(self) -> None:
        cases = (
            (1, 1, "previous_scope_revision is forbidden for scope_revision 1"),
            (2, None, "scope_revision 2 requires previous_scope_revision 1"),
            (3, 1, "scope_revision 3 requires previous_scope_revision 2"),
        )
        for scope_revision, previous_revision, expected in cases:
            with (
                self.subTest(scope_revision=scope_revision),
                tempfile.TemporaryDirectory() as tmp_dir,
            ):
                work_dir = self.write_valid_work(
                    Path(tmp_dir),
                    artifact_revision=scope_revision,
                    scope_revision=scope_revision,
                    previous_scope_revision=previous_revision,
                    previous_status="approved",
                    status="implementing",
                )
                result = self.run_checker(work_dir)

                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(expected, result.stdout)

    def test_scope_revision_can_restart_from_approved_or_published(self) -> None:
        for previous_status in ("approved", "published"):
            with (
                self.subTest(previous_status=previous_status),
                tempfile.TemporaryDirectory() as tmp_dir,
            ):
                work_dir = self.write_valid_work(
                    Path(tmp_dir),
                    artifact_revision=2,
                    scope_revision=2,
                    previous_scope_revision=1,
                    previous_status=previous_status,
                    status="approved",
                )
                result = self.run_checker(work_dir)

                self.assertEqual(
                    result.returncode,
                    0,
                    result.stdout + result.stderr,
                )
                self.assertIn("Agent work contract: OK", result.stdout)

    def test_blocking_review_fix_can_return_to_implementation(self) -> None:
        for previous_status in ("verifying", "accepted"):
            with self.subTest(previous_status=previous_status), tempfile.TemporaryDirectory() as tmp_dir:
                work_dir = self.write_valid_work(
                    Path(tmp_dir),
                    previous_status=previous_status,
                    status="implementing",
                )
                result = self.run_checker(work_dir)

                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("review-fix transition requires blocking_reference", result.stdout)

        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(
                Path(tmp_dir),
                previous_status="accepted",
                status="implementing",
                blocking_reference="review finding R-7",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Agent work contract: OK", result.stdout)

    def test_declared_nested_history_and_patch_artifacts_are_rejected(self) -> None:
        cases = ("history/scope-r2.md", "review.patch")
        for relative_path in cases:
            with (
                self.subTest(path=relative_path),
                tempfile.TemporaryDirectory() as tmp_dir,
            ):
                work_dir = self.write_valid_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(
                        'scope = "scope.md"',
                        f'scope = "scope.md"\nextra = "{relative_path}"',
                    ),
                    encoding="utf-8",
                )
                artifact = work_dir / relative_path
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_text("- `scope_revision`: 1\n", encoding="utf-8")
                result = self.run_checker(work_dir)

                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertRegex(result.stdout, "retained scope revision|raw diff/patch")

    def test_artifact_paths_must_remain_inside_work_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            work_dir = self.write_valid_work(root)
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8")
                .replace('scope = "scope.md"', 'scope = "../outside.md"')
                .replace(
                    'requirements_source = "scope.md"',
                    'requirements_source = "../outside.md"',
                ),
                encoding="utf-8",
            )
            (root / "outside.md").write_text(
                "- `scope_revision`: 1\n",
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("artifact path must be relative and contained", result.stdout)

    def test_artifact_symlink_cannot_escape_work_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            work_dir = self.write_valid_work(root)
            outside = root / "outside.md"
            outside.write_text("- `scope_revision`: 1\n", encoding="utf-8")
            (work_dir / "scope.md").unlink()
            (work_dir / "scope.md").symlink_to(outside)
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("declared artifact resolves outside work directory", result.stdout)

    def test_symlink_directory_is_forbidden_work_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            work_dir = self.write_valid_work(root)
            outside = root / "outside"
            outside.mkdir()
            (outside / "history.diff").write_text(
                "diff --git a/example b/example\n",
                encoding="utf-8",
            )
            (work_dir / "linked-history").symlink_to(outside, target_is_directory=True)
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("symlink work artifacts are forbidden", result.stdout)

    def test_requirements_source_requires_unique_definitions(self) -> None:
        cases = (
            ("References BR-001 and AC-001.\n- `scope_revision`: 1\n", "not declared"),
            (
                "- `scope_revision`: 1\n- BR-001: One.\n- BR-001: Two.\n- AC-001: Done.\n",
                "duplicate requirement definitions: BR-001",
            ),
        )
        for content, expected in cases:
            with (
                self.subTest(expected=expected),
                tempfile.TemporaryDirectory() as tmp_dir,
            ):
                work_dir = self.write_valid_work(Path(tmp_dir))
                (work_dir / "scope.md").write_text(content, encoding="utf-8")
                result = self.run_checker(work_dir)

                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(expected, result.stdout)

    def test_downstream_artifact_cannot_copy_requirement_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'scope = "scope.md"', 'scope = "scope.md"\nplan = "plan.md"'
                ),
                encoding="utf-8",
            )
            (work_dir / "plan.md").write_text(
                "- `scope_revision`: 1\n- BR-001: copied definition\n",
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "requirement definitions are allowed only in requirements_source",
            result.stdout,
        )

    def test_integer_fields_reject_toml_booleans(self) -> None:
        cases = (
            (
                "schema_version = 1",
                "schema_version = true",
                "schema_version must be 1",
            ),
            (
                "scope_revision = 1",
                "scope_revision = true",
                "scope_revision must be a positive integer",
            ),
            (
                "max_artifact_lines = 300",
                "max_artifact_lines = true",
                "max_artifact_lines must be a positive integer",
            ),
            (
                "max_total_artifact_lines = 600",
                "max_total_artifact_lines = true",
                "max_total_artifact_lines must be a positive integer",
            ),
        )
        for old, new, expected in cases:
            with self.subTest(field=old), tempfile.TemporaryDirectory() as tmp_dir:
                work_dir = self.write_valid_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(old, new),
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir)

                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(expected, result.stdout)

    def test_published_explicit_workdir_requires_expected_head_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(
                Path(tmp_dir),
                previous_status="accepted",
                status="published",
            )
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'status = "published"\n',
                    f'status = "published"\nreviewed_sha = "{"0" * 40}"\n',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("published validation requires expected head SHA", result.stdout)

    def test_total_artifact_line_budget_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8")
                .replace(
                    "max_total_artifact_lines = 600",
                    "max_total_artifact_lines = 10",
                )
                .replace('scope = "scope.md"', 'scope = "scope.md"\nplan = "plan.md"'),
                encoding="utf-8",
            )
            (work_dir / "plan.md").write_text(
                "- `scope_revision`: 1\n" + "line\n" * 5,
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("total artifact lines", result.stdout)

    def test_cli_rejects_tracked_active_work_artifacts(self) -> None:
        for commit_artifact in (False, True):
            with (
                self.subTest(committed=commit_artifact),
                tempfile.TemporaryDirectory() as tmp_dir,
            ):
                repo_root = Path(tmp_dir) / "repo"
                repo_root.mkdir()
                self.initialize_git_repo(repo_root)
                work_parent = repo_root / ".codex" / "work"
                work_parent.mkdir(parents=True)
                work_dir = self.write_valid_work(work_parent)
                subprocess.run(
                    ("git", "add", "-f", str(work_dir / "task.toml")),
                    cwd=repo_root,
                    check=True,
                )
                if commit_artifact:
                    subprocess.run(
                        (
                            "git",
                            "-c",
                            "user.name=Codex Tests",
                            "-c",
                            "user.email=codex-tests@example.invalid",
                            "commit",
                            "-m",
                            "leaked work artifact",
                        ),
                        cwd=repo_root,
                        check=True,
                        capture_output=True,
                    )

                result = subprocess.run(
                    (sys.executable, self.checker, "--repo-root", repo_root),
                    cwd=self.repo_root,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(
                    "tracked active work artifacts are forbidden",
                    result.stdout,
                )

    def test_cli_rejects_work_artifact_removed_after_feature_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            repo_root.mkdir()
            self.initialize_git_repo(repo_root)
            work_parent = repo_root / ".codex" / "work"
            work_parent.mkdir(parents=True)
            work_dir = self.write_valid_work(work_parent)
            leaked_artifact = work_dir / "leaked-review.md"
            leaked_artifact.write_text("temporary\n", encoding="utf-8")
            subprocess.run(
                ("git", "add", "-f", str(leaked_artifact)),
                cwd=repo_root,
                check=True,
            )
            for message in ("leak work artifact", "remove work artifact"):
                subprocess.run(
                    (
                        "git",
                        "-c",
                        "user.name=Codex Tests",
                        "-c",
                        "user.email=codex-tests@example.invalid",
                        "commit",
                        "-m",
                        message,
                    ),
                    cwd=repo_root,
                    check=True,
                    capture_output=True,
                )
                if message == "leak work artifact":
                    subprocess.run(
                        ("git", "rm", str(leaked_artifact)),
                        cwd=repo_root,
                        check=True,
                        capture_output=True,
                    )

            result = subprocess.run(
                (sys.executable, self.checker, "--repo-root", repo_root),
                cwd=self.repo_root,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("committed work artifact history is forbidden", result.stdout)

    def test_cli_rejects_symlink_active_work_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo_root = root / "repo"
            repo_root.mkdir()
            self.initialize_git_repo(repo_root)
            work_parent = repo_root / ".codex" / "work"
            work_parent.mkdir(parents=True)
            external_parent = root / "external"
            external_parent.mkdir()
            external_work_dir = self.write_valid_work(external_parent)
            (work_parent / "test-feature").symlink_to(
                external_work_dir,
                target_is_directory=True,
            )

            result = subprocess.run(
                (sys.executable, self.checker, "--repo-root", repo_root),
                cwd=self.repo_root,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("active work directory cannot be a symlink", result.stdout)

    def test_changed_file_must_belong_to_a_batch_after_planning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            repo_root.mkdir()
            self.initialize_git_repo(repo_root)
            work_parent = repo_root / ".codex" / "work"
            work_parent.mkdir(parents=True)
            work_dir = self.write_valid_work(work_parent)
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'allowed_files = ["scripts/check_agent_work.py"]',
                    'allowed_files = ["scripts/check_agent_work.py", "src/runtime.py"]',
                    1,
                ),
                encoding="utf-8",
            )
            runtime_file = repo_root / "src" / "runtime.py"
            runtime_file.parent.mkdir(exist_ok=True)
            runtime_file.write_text("changed = True\n", encoding="utf-8")

            result = subprocess.run(
                (sys.executable, self.checker, "--repo-root", repo_root),
                cwd=self.repo_root,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("changed files outside batch ownership: src/runtime.py", result.stdout)

    def test_batch_dependency_must_reference_declared_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    "dependencies = []",
                    'dependencies = ["UNKNOWN"]',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("batch B1 has unknown dependencies: UNKNOWN", result.stdout)

    def test_batch_dependency_graph_rejects_self_and_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    "dependencies = []",
                    'dependencies = ["B1"]',
                ),
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("batch B1 cannot depend on itself", result.stdout)

        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = self.write_valid_work(Path(tmp_dir))
            manifest = work_dir / "task.toml"
            manifest_text = manifest.read_text(encoding="utf-8").replace(
                "dependencies = []",
                'dependencies = ["B2"]',
            )
            second_batch = (
                manifest_text.split("[[batches]]", maxsplit=1)[1]
                .replace('id = "B1"', 'id = "B2"')
                .replace('items = ["AW-001"]', 'items = ["AW-002"]')
                .replace('dependencies = ["B2"]', 'dependencies = ["B1"]')
            )
            manifest.write_text(
                manifest_text + "\n[[batches]]" + second_batch,
                encoding="utf-8",
            )
            result = self.run_checker(work_dir)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("batch dependency cycle", result.stdout)

    def test_overlapping_batch_ownership_requires_dependency_order(self) -> None:
        for ordered in (False, True):
            with (
                self.subTest(ordered=ordered),
                tempfile.TemporaryDirectory() as tmp_dir,
            ):
                work_dir = self.write_valid_work(Path(tmp_dir))
                manifest = work_dir / "task.toml"
                manifest_text = manifest.read_text(encoding="utf-8")
                second_batch = (
                    manifest_text.split("[[batches]]", maxsplit=1)[1]
                    .replace('id = "B1"', 'id = "B2"')
                    .replace('items = ["AW-001"]', 'items = ["AW-002"]')
                    .replace(
                        "dependencies = []",
                        'dependencies = ["B1"]' if ordered else "dependencies = []",
                    )
                )
                manifest.write_text(
                    manifest_text + "\n[[batches]]" + second_batch,
                    encoding="utf-8",
                )
                result = self.run_checker(work_dir)

                if ordered:
                    self.assertEqual(
                        result.returncode,
                        0,
                        result.stdout + result.stderr,
                    )
                else:
                    self.assertEqual(
                        result.returncode,
                        1,
                        result.stdout + result.stderr,
                    )
                    self.assertIn(
                        "unordered batches B1 and B2 overlap files",
                        result.stdout,
                    )


if __name__ == "__main__":
    unittest.main()
