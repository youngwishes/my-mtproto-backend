#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import tomllib
from pathlib import Path

SCOPE_REVISION_LINE = re.compile(
    r"^\s*(?:[-*]\s+)?`?scope_revision`?\s*(?::|=)",
    re.IGNORECASE,
)
SCOPE_REVISION_DECLARATION = re.compile(
    r"\s*(?:[-*]\s+)?`?scope_revision`?\s*(?::|=)\s*([1-9]\d*)\s*",
    re.IGNORECASE,
)
RAW_DIFF_SIGNATURE = re.compile(
    r"^diff --git(?:\s|$)|^---[^\n]*\n\+\+\+[^\n]*(?:\n|$)|^GIT binary patch$",
    re.MULTILINE,
)
REQUIREMENT_ID = re.compile(r"\b(?:BR|AC)-\d{3}\b")
REQUIREMENT_DEFINITION = re.compile(
    r"^\s*(?:[-*]\s+)?(?:\*\*)?((?:BR|AC)-\d{3})(?:\*\*)?\s*(?::|[-–—])",
    re.MULTILINE,
)
RETAINED_REVISION = re.compile(r"(?:-r\d+|-revision-?\d+)\.md$", re.IGNORECASE)
ALLOWED_STATUS_TRANSITIONS = frozenset(
    {
        ("draft", "approved"),
        ("approved", "implementing"),
        ("implementing", "verifying"),
        ("verifying", "implementing"),
        ("verifying", "accepted"),
        ("accepted", "implementing"),
        ("accepted", "published"),
        ("published", "closed"),
    }
)
VALID_STATUSES = frozenset(
    {
        "draft",
        "approved",
        "implementing",
        "verifying",
        "accepted",
        "published",
        "closed",
    }
)
TASK_FIELDS = frozenset(
    {
        "schema_version",
        "feature_slug",
        "scope_revision",
        "previous_scope_revision",
        "previous_status",
        "status",
        "blocking_reference",
        "requirements_source",
        "requirement_ids",
        "allowed_files",
        "non_goals",
        "budget",
        "completion",
        "max_artifact_lines",
        "max_total_artifact_lines",
        "reviewed_sha",
        "artifacts",
        "batches",
    }
)
BATCH_FIELDS = frozenset(
    {
        "id",
        "items",
        "requirements",
        "allowed_files",
        "dependencies",
        "non_goals",
        "budget",
        "completion",
    }
)


def is_string_list(value: object, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and bool(item) for item in value)
    )


def duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def is_safe_artifact_path(value: str) -> bool:
    path = Path(value)
    return (
        not path.is_absolute()
        and value not in {"", "."}
        and ".." not in path.parts
    )


def validate_manifest_shape(task: dict[str, object], manifest: Path) -> list[str]:
    violations: list[str] = []
    if unknown_fields := sorted(set(task) - TASK_FIELDS):
        violations.append(
            f"{manifest}: unknown task fields: {', '.join(unknown_fields)}"
        )
    if (
        type(task.get("schema_version")) is not int
        or task.get("schema_version") != 1
    ):
        violations.append(f"{manifest}: schema_version must be 1")
    if type(task.get("scope_revision")) is not int or task["scope_revision"] < 1:
        violations.append(f"{manifest}: scope_revision must be a positive integer")
    previous_scope_revision = task.get("previous_scope_revision")
    if previous_scope_revision is not None and (
        type(previous_scope_revision) is not int or previous_scope_revision < 1
    ):
        violations.append(
            f"{manifest}: previous_scope_revision must be a positive integer"
        )
    status = task.get("status")
    if not isinstance(status, str) or status not in VALID_STATUSES:
        violations.append(f"{manifest}: status must be one of {sorted(VALID_STATUSES)}")
    previous_status = task.get("previous_status")
    if previous_status is not None and not isinstance(previous_status, str):
        violations.append(f"{manifest}: previous_status must be a string")
    for field in ("feature_slug", "requirements_source"):
        if not isinstance(task.get(field), str) or not task[field]:
            violations.append(f"{manifest}: {field} must be a non-empty string")
    for field in ("requirement_ids", "allowed_files"):
        allow_empty = status == "draft" and field == "requirement_ids"
        if not is_string_list(task.get(field), allow_empty=allow_empty):
            qualifier = "a string array" if allow_empty else "a non-empty string array"
            violations.append(f"{manifest}: {field} must be {qualifier}")
    if not is_string_list(task.get("non_goals")):
        violations.append(
            f"{manifest}: task packet is missing non-empty non_goals"
        )
    for field in ("budget", "completion"):
        if not isinstance(task.get(field), str) or not task[field]:
            violations.append(
                f"{manifest}: task packet is missing non-empty {field}"
            )
    requirement_ids = task.get("requirement_ids")
    if isinstance(requirement_ids, list) and all(
        isinstance(requirement_id, str) for requirement_id in requirement_ids
    ):
        invalid_requirement_ids = sorted(
            {
                requirement_id
                for requirement_id in requirement_ids
                if not REQUIREMENT_ID.fullmatch(requirement_id)
            }
        )
        if invalid_requirement_ids:
            violations.append(
                f"{manifest}: invalid requirement_ids: "
                f"{', '.join(invalid_requirement_ids)}"
            )
        duplicate_requirement_ids = duplicate_values(requirement_ids)
        if duplicate_requirement_ids:
            violations.append(
                f"{manifest}: duplicate requirement_ids: "
                f"{', '.join(duplicate_requirement_ids)}"
            )
    max_artifact_lines = task.get("max_artifact_lines")
    if type(max_artifact_lines) is not int or max_artifact_lines < 1:
        violations.append(
            f"{manifest}: max_artifact_lines must be a positive integer"
        )
    max_total_artifact_lines = task.get("max_total_artifact_lines")
    if type(max_total_artifact_lines) is not int or max_total_artifact_lines < 1:
        violations.append(
            f"{manifest}: max_total_artifact_lines must be a positive integer"
        )
    artifacts = task.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts or not all(
        isinstance(name, str)
        and bool(name)
        and isinstance(path, str)
        and bool(path)
        for name, path in artifacts.items()
    ):
        violations.append(f"{manifest}: artifacts must be a non-empty string table")
    elif unsafe_paths := sorted(
        path for path in artifacts.values() if not is_safe_artifact_path(path)
    ):
        violations.append(
            f"{manifest}: artifact path must be relative and contained: "
            f"{', '.join(unsafe_paths)}"
        )
    elif "task.toml" in artifacts.values():
        violations.append(f"{manifest}: task.toml cannot be a declared artifact")
    elif duplicate_artifact_paths := duplicate_values(list(artifacts.values())):
        violations.append(
            f"{manifest}: duplicate artifact paths: "
            f"{', '.join(duplicate_artifact_paths)}"
        )

    batches = task.get("batches", [])
    if not isinstance(batches, list) or not all(
        isinstance(batch, dict) for batch in batches
    ):
        violations.append(f"{manifest}: batches must be an array of tables")
        return violations
    if (
        isinstance(status, str)
        and status not in {"draft", "approved"}
        and not batches
    ):
        violations.append(
            f"{manifest}: implementation lifecycle requires at least one batch"
        )
    batch_ids = [
        batch["id"] for batch in batches if isinstance(batch.get("id"), str)
    ]
    duplicate_batch_ids = duplicate_values(batch_ids)
    if duplicate_batch_ids:
        violations.append(
            f"{manifest}: duplicate batch ids: {', '.join(duplicate_batch_ids)}"
        )
    item_ids = [
        item
        for batch in batches
        if isinstance(batch.get("items"), list)
        for item in batch["items"]
        if isinstance(item, str)
    ]
    duplicate_item_ids = duplicate_values(item_ids)
    if duplicate_item_ids:
        violations.append(
            f"{manifest}: duplicate item ids: {', '.join(duplicate_item_ids)}"
        )
    for index, batch in enumerate(batches, start=1):
        batch_id = batch.get("id")
        if not isinstance(batch_id, str) or not batch_id:
            violations.append(
                f"{manifest}: batch {index} is missing non-empty id"
            )
        label = batch_id or index
        if unknown_fields := sorted(set(batch) - BATCH_FIELDS):
            violations.append(
                f"{manifest}: batch {label} has unknown fields: "
                f"{', '.join(unknown_fields)}"
            )
        for field in ("items", "requirements", "allowed_files", "non_goals"):
            if not is_string_list(batch.get(field)):
                violations.append(
                    f"{manifest}: batch {label} is missing non-empty {field}"
                )
        if not is_string_list(batch.get("dependencies"), allow_empty=True):
            violations.append(f"{manifest}: batch {label} is missing dependencies")
        for field in ("budget", "completion"):
            if not isinstance(batch.get(field), str) or not batch[field]:
                violations.append(
                    f"{manifest}: batch {label} is missing non-empty {field}"
                )
    return violations


def check_work_dir(
    work_dir: Path,
    *,
    changed_files: set[str] | None = None,
    tracked_work_files: set[str] | None = None,
    historical_work_files: set[str] | None = None,
    expected_head_sha: str | None = None,
) -> list[str]:
    if work_dir.is_symlink():
        return [f"{work_dir}: active work directory cannot be a symlink"]
    manifest = work_dir / "task.toml"
    if not manifest.is_file():
        return [f"{manifest}: task manifest is missing"]

    try:
        manifest_text = manifest.read_text(encoding="utf-8")
        task = tomllib.loads(manifest_text)
    except tomllib.TOMLDecodeError as error:
        return [f"{manifest}: invalid TOML: {error}"]
    violations = validate_manifest_shape(task, manifest)
    max_artifact_lines = task.get("max_artifact_lines")
    manifest_line_count = len(manifest_text.splitlines())
    if RAW_DIFF_SIGNATURE.search(manifest_text):
        violations.append(f"{manifest}: raw diff/patch content is forbidden")
    if copied_definitions := sorted(
        set(REQUIREMENT_DEFINITION.findall(manifest_text))
    ):
        violations.append(
            f"{manifest}: requirement definitions are allowed only in "
            f"requirements_source: {', '.join(copied_definitions)}"
        )
    if (
        type(max_artifact_lines) is int
        and manifest_line_count > max_artifact_lines
    ):
        violations.append(
            f"{manifest}: {manifest_line_count} lines exceeds max_artifact_lines "
            f"{max_artifact_lines}"
        )
    if violations:
        return violations
    feature_slug = task.get("feature_slug")
    if feature_slug != work_dir.name:
        violations.append(
            f"{manifest}: feature_slug {feature_slug} does not match work directory "
            f"{work_dir.name}"
        )
    transition = (task.get("previous_status"), task.get("status"))
    scope_revision = task.get("scope_revision")
    previous_scope_revision = task.get("previous_scope_revision")
    if scope_revision == 1 and previous_scope_revision is not None:
        violations.append(
            f"{manifest}: previous_scope_revision is forbidden for scope_revision 1"
        )
    elif scope_revision > 1 and previous_scope_revision != scope_revision - 1:
        violations.append(
            f"{manifest}: scope_revision {scope_revision} requires "
            f"previous_scope_revision {scope_revision - 1}"
        )
    is_initial_draft = transition == (None, "draft") and scope_revision == 1
    is_approved_scope_change = (
        transition[1] == "approved"
        and transition[0]
        in {"approved", "implementing", "verifying", "accepted", "published"}
        and isinstance(scope_revision, int)
        and previous_scope_revision == scope_revision - 1
    )
    if (
        transition not in ALLOWED_STATUS_TRANSITIONS
        and not is_approved_scope_change
        and not is_initial_draft
    ):
        violations.append(
            f"{manifest}: invalid status transition: {transition[0]} -> {transition[1]}"
        )
    is_review_fix = transition in {
        ("verifying", "implementing"),
        ("accepted", "implementing"),
    }
    blocking_reference = task.get("blocking_reference")
    if is_review_fix and (
        not isinstance(blocking_reference, str) or not blocking_reference.strip()
    ):
        violations.append(
            f"{manifest}: review-fix transition requires blocking_reference"
        )
    elif not is_review_fix and "blocking_reference" in task:
        violations.append(
            f"{manifest}: blocking_reference is allowed only for a review-fix transition"
        )
    reviewed_sha = task.get("reviewed_sha", "")
    if task.get("status") == "published":
        if not isinstance(reviewed_sha, str) or not re.fullmatch(
            r"[0-9a-f]{40}", reviewed_sha
        ):
            violations.append(
                f"{manifest}: published task requires a 40-character reviewed_sha"
            )
        elif expected_head_sha is None:
            violations.append(
                f"{manifest}: published validation requires expected head SHA"
            )
        elif reviewed_sha != expected_head_sha:
            violations.append(
                f"{manifest}: reviewed_sha does not match expected head SHA "
                f"{expected_head_sha}"
            )
    elif "reviewed_sha" in task:
        violations.append(
            f"{manifest}: reviewed_sha is allowed only for published status"
        )
    if task.get("status") == "closed":
        violations.append(
            f"{work_dir}: closed task directory must be removed; durable history "
            "belongs in the Pull Request and canonical documentation"
        )
    work_entries = sorted(work_dir.rglob("*"))
    for symlink in (path for path in work_entries if path.is_symlink()):
        violations.append(
            f"{symlink}: symlink work artifacts are forbidden"
        )
    retained_revisions = sorted(
        path
        for path in work_entries
        if path.is_file() and RETAINED_REVISION.search(path.name)
    )
    for retained_revision in retained_revisions:
        violations.append(
            f"{retained_revision}: retained scope revision is forbidden; "
            "keep only the current requirements owner"
        )
    for raw_diff_or_patch in (
        path
        for path in work_entries
        if path.is_file() and path.suffix.lower() in {".diff", ".patch"}
    ):
        violations.append(
            f"{raw_diff_or_patch}: raw diff/patch artifacts are forbidden; inspect the "
            "working tree or Pull Request directly"
        )
    task_allowed_files = set(task.get("allowed_files", []))
    if tracked_work_files:
        violations.append(
            f"{manifest}: tracked active work artifacts are forbidden: "
            f"{', '.join(sorted(tracked_work_files))}"
        )
    if historical_work_files:
        violations.append(
            f"{manifest}: committed work artifact history is forbidden: "
            f"{', '.join(sorted(historical_work_files))}"
        )
    if changed_files is not None:
        unexpected_changed_files = sorted(changed_files - task_allowed_files)
        if unexpected_changed_files:
            violations.append(
                f"{manifest}: changed files outside task ownership: "
                f"{', '.join(unexpected_changed_files)}"
            )
    task_requirements = set(task.get("requirement_ids", []))
    batches = task.get("batches", [])
    batch_ids = {batch.get("id") for batch in batches}
    for batch in batches:
        unknown_dependencies = sorted(set(batch["dependencies"]) - batch_ids)
        if unknown_dependencies:
            violations.append(
                f"{manifest}: batch {batch.get('id')} has unknown dependencies: "
                f"{', '.join(unknown_dependencies)}"
            )
        if batch.get("id") in batch["dependencies"]:
            violations.append(
                f"{manifest}: batch {batch.get('id')} cannot depend on itself"
            )
        items = batch.get("items", [])
        if len(items) > 2:
            violations.append(
                f"{manifest}: batch {batch.get('id')} assigns {len(items)} items; "
                "maximum is 2"
            )
        unexpected_files = sorted(
            set(batch.get("allowed_files", [])) - task_allowed_files
        )
        if unexpected_files:
            violations.append(
                f"{manifest}: batch {batch.get('id')} contains files outside task "
                f"ownership: {', '.join(unexpected_files)}"
            )
        unexpected_requirements = sorted(
            set(batch.get("requirements", [])) - task_requirements
        )
        if unexpected_requirements:
            violations.append(
                f"{manifest}: batch {batch.get('id')} contains unapproved "
                f"requirements: {', '.join(unexpected_requirements)}"
            )
    dependency_graph = {
        batch["id"]: set(batch["dependencies"]) & batch_ids - {batch["id"]}
        for batch in batches
        if isinstance(batch.get("id"), str)
    }
    remaining_dependencies = {
        batch_id: set(dependencies)
        for batch_id, dependencies in dependency_graph.items()
    }
    while ready_batches := {
        batch_id
        for batch_id, dependencies in remaining_dependencies.items()
        if not dependencies
    }:
        for batch_id in ready_batches:
            remaining_dependencies.pop(batch_id)
        for dependencies in remaining_dependencies.values():
            dependencies.difference_update(ready_batches)
    if remaining_dependencies:
        violations.append(
            f"{manifest}: batch dependency cycle: "
            f"{', '.join(sorted(remaining_dependencies))}"
        )
    if changed_files is not None and task.get("status") not in {"draft", "approved"}:
        batch_allowed_files = {
            allowed_file
            for batch in batches
            for allowed_file in batch.get("allowed_files", [])
        }
        unexpected_batch_files = sorted(changed_files - batch_allowed_files)
        if unexpected_batch_files:
            violations.append(
                f"{manifest}: changed files outside batch ownership: "
                f"{', '.join(unexpected_batch_files)}"
            )
    expected_revision = scope_revision
    max_total_artifact_lines = task.get("max_total_artifact_lines")
    artifacts = task.get("artifacts", {})
    requirements_source = task.get("requirements_source")
    if requirements_source not in artifacts.values():
        violations.append(
            f"{manifest}: requirements_source must name one declared artifact"
        )
    allowed_work_artifacts = {"task.toml", *artifacts.values()}
    for work_artifact in sorted(
        path for path in work_entries if path.is_file()
    ):
        relative_artifact = work_artifact.relative_to(work_dir).as_posix()
        if relative_artifact not in allowed_work_artifacts:
            violations.append(
                f"{work_dir}: undeclared work artifact: {relative_artifact}"
            )
    total_artifact_lines = manifest_line_count
    readable_artifacts: dict[str, str] = {}
    resolved_work_dir = work_dir.resolve()
    for artifact_name in artifacts.values():
        artifact = work_dir / artifact_name
        if not artifact.is_file():
            if task.get("status") == "draft" and artifact_name == requirements_source:
                continue
            violations.append(f"{artifact}: declared artifact is missing")
            continue
        try:
            artifact.resolve().relative_to(resolved_work_dir)
        except ValueError:
            violations.append(
                f"{artifact}: declared artifact resolves outside work directory"
            )
            continue
        try:
            artifact_text = artifact.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            violations.append(
                f"{artifact}: declared artifact must be readable UTF-8 text: {error}"
            )
            continue
        readable_artifacts[artifact_name] = artifact_text
        if RAW_DIFF_SIGNATURE.search(artifact_text):
            violations.append(
                f"{artifact}: raw diff/patch artifacts are forbidden; inspect the "
                "working tree or Pull Request directly"
            )
        line_count = len(artifact_text.splitlines())
        total_artifact_lines += line_count
        if line_count > max_artifact_lines:
            violations.append(
                f"{artifact}: {line_count} lines exceeds max_artifact_lines "
                f"{max_artifact_lines}"
            )
        revision_lines = [
            line
            for line in artifact_text.splitlines()
            if SCOPE_REVISION_LINE.search(line)
        ]
        if not revision_lines:
            violations.append(
                f"{artifact}: declared artifact must state scope_revision"
            )
        elif len(revision_lines) != 1:
            violations.append(
                f"{artifact}: declared artifact must state scope_revision exactly once"
            )
        else:
            revision_match = SCOPE_REVISION_DECLARATION.fullmatch(revision_lines[0])
            if revision_match is None:
                violations.append(
                    f"{artifact}: scope_revision must be one positive integer"
                )
            elif int(revision_match.group(1)) != expected_revision:
                violations.append(
                    f"{artifact}: scope_revision {revision_match.group(1)} does not "
                    f"match task.toml revision {expected_revision}"
                )
    if total_artifact_lines > max_total_artifact_lines:
        violations.append(
            f"{work_dir}: total artifact lines {total_artifact_lines} exceeds "
            f"max_total_artifact_lines {max_total_artifact_lines}"
        )
    requirements_artifact = work_dir / requirements_source
    if task.get("status") != "draft" and requirements_source in readable_artifacts:
        source_definitions = REQUIREMENT_DEFINITION.findall(
            readable_artifacts[requirements_source]
        )
        duplicate_definitions = duplicate_values(source_definitions)
        if duplicate_definitions:
            violations.append(
                f"{requirements_artifact}: duplicate requirement definitions: "
                f"{', '.join(duplicate_definitions)}"
            )
        source_ids = set(source_definitions)
        manifest_ids = set(task_requirements)
        undeclared_ids = sorted(manifest_ids - source_ids)
        if undeclared_ids:
            violations.append(
                f"{manifest}: requirement_ids not declared in "
                f"{requirements_source}: {', '.join(undeclared_ids)}"
            )
        missing_ids = sorted(source_ids - manifest_ids)
        if missing_ids:
            violations.append(
                f"{manifest}: requirements source IDs missing from task.toml: "
                f"{', '.join(missing_ids)}"
            )
    for artifact_name, artifact_text in readable_artifacts.items():
        if artifact_name == requirements_source:
            continue
        copied_definitions = sorted(set(REQUIREMENT_DEFINITION.findall(artifact_text)))
        if copied_definitions:
            violations.append(
                f"{work_dir / artifact_name}: requirement definitions are allowed "
                f"only in requirements_source: {', '.join(copied_definitions)}"
            )
    return violations


def resolve_work_dir(repo_root: Path) -> Path:
    branch = subprocess.run(
        ("git", "branch", "--show-current"),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    prefix = "codex/"
    if not branch.startswith(prefix) or branch == prefix:
        raise ValueError("current branch must use codex/<feature-slug>")
    return repo_root / ".codex" / "work" / branch.removeprefix(prefix)


def git_changed_files(repo_root: Path, work_dir: Path) -> set[str]:
    tracked_commands = (
        ("git", "diff", "--no-renames", "--name-only", "-z"),
        ("git", "diff", "--cached", "--no-renames", "--name-only", "-z"),
    )
    changed_files: set[str] = set()
    merge_base = subprocess.run(
        ("git", "merge-base", "HEAD", "main"),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    committed_output = subprocess.run(
        (
            "git",
            "diff",
            "--no-renames",
            "--name-only",
            "-z",
            f"{merge_base}..HEAD",
        ),
        cwd=repo_root,
        check=True,
        capture_output=True,
    ).stdout
    changed_files.update(
        path.decode("utf-8") for path in committed_output.split(b"\0") if path
    )
    for command in tracked_commands:
        output = subprocess.run(
            command,
            cwd=repo_root,
            check=True,
            capture_output=True,
        ).stdout
        changed_files.update(
            path.decode("utf-8") for path in output.split(b"\0") if path
        )
    work_prefix = f"{work_dir.relative_to(repo_root).as_posix()}/"
    output = subprocess.run(
        ("git", "ls-files", "--others", "--exclude-standard", "-z"),
        cwd=repo_root,
        check=True,
        capture_output=True,
    ).stdout
    untracked_files = {
        path.decode("utf-8") for path in output.split(b"\0") if path
    }
    changed_files.update(
        path for path in untracked_files if not path.startswith(work_prefix)
    )
    return changed_files


def git_tracked_work_files(repo_root: Path, work_dir: Path) -> set[str]:
    relative_work_dir = work_dir.relative_to(repo_root).as_posix()
    output = subprocess.run(
        ("git", "ls-files", "-z", "--", relative_work_dir),
        cwd=repo_root,
        check=True,
        capture_output=True,
    ).stdout
    return {path.decode("utf-8") for path in output.split(b"\0") if path}


def git_historical_work_files(repo_root: Path, work_dir: Path) -> set[str]:
    merge_base = subprocess.run(
        ("git", "merge-base", "HEAD", "main"),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    relative_work_dir = work_dir.relative_to(repo_root).as_posix()
    output = subprocess.run(
        (
            "git",
            "log",
            "--format=",
            "--name-only",
            "--no-renames",
            "-z",
            f"{merge_base}..HEAD",
            "--",
            relative_work_dir,
        ),
        cwd=repo_root,
        check=True,
        capture_output=True,
    ).stdout
    return {
        decoded
        for value in output.split(b"\0")
        if value and (decoded := value.decode("utf-8").strip())
    }


def git_head_sha(repo_root: Path) -> str:
    return subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate active Codex task work")
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-head-sha")
    args = parser.parse_args()

    use_git_state = args.work_dir is None
    try:
        work_dir = args.work_dir or resolve_work_dir(args.repo_root)
        changed_files = (
            git_changed_files(args.repo_root, work_dir) if use_git_state else None
        )
        tracked_work_files = (
            git_tracked_work_files(args.repo_root, work_dir)
            if use_git_state
            else None
        )
        historical_work_files = (
            git_historical_work_files(args.repo_root, work_dir)
            if use_git_state
            else None
        )
        expected_head_sha = args.expected_head_sha
        if use_git_state and expected_head_sha is None:
            expected_head_sha = git_head_sha(args.repo_root)
    except (subprocess.CalledProcessError, ValueError) as error:
        print(f"Agent work contract: {error}")
        return 1

    violations = check_work_dir(
        work_dir,
        changed_files=changed_files,
        tracked_work_files=tracked_work_files,
        historical_work_files=historical_work_files,
        expected_head_sha=expected_head_sha,
    )
    if violations:
        for violation in violations:
            print(violation)
        return 1

    print("Agent work contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
