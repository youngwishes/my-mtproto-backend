#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import tomllib
from pathlib import Path

REQUIREMENT_ID = re.compile(r"(?:BR|AC)-\d{3}")
VALID_STATUSES = frozenset(
    {"draft", "approved", "implementing", "verifying", "accepted", "published"}
)


def is_string_list(value: object, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and bool(item) for item in value)
    )


def duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return sorted(repeated)


def validate_manifest(task: dict[str, object], manifest: Path) -> list[str]:
    violations: list[str] = []
    if not isinstance(task.get("feature_slug"), str) or not task["feature_slug"]:
        violations.append(f"{manifest}: feature_slug must be a non-empty string")
    revision = task.get("scope_revision")
    if type(revision) is not int or revision < 1:
        violations.append(f"{manifest}: scope_revision must be a positive integer")
    status = task.get("status")
    if not isinstance(status, str) or status not in VALID_STATUSES:
        violations.append(f"{manifest}: status must be one of {sorted(VALID_STATUSES)}")
    if (
        not isinstance(task.get("requirements_source"), str)
        or not task["requirements_source"]
    ):
        violations.append(f"{manifest}: requirements_source must be a non-empty string")

    requirement_ids = task.get("requirement_ids")
    allow_empty_requirements = status == "draft"
    if not is_string_list(requirement_ids, allow_empty=allow_empty_requirements):
        violations.append(f"{manifest}: requirement_ids must be a string array")
        task_requirements: set[str] = set()
    else:
        task_requirements = set(requirement_ids)
        invalid_ids = sorted(
            requirement_id
            for requirement_id in task_requirements
            if not REQUIREMENT_ID.fullmatch(requirement_id)
        )
        repeated_ids = duplicates(requirement_ids)
        if invalid_ids or repeated_ids:
            details = ", ".join(invalid_ids + repeated_ids)
            violations.append(f"{manifest}: invalid requirement_ids: {details}")

    allowed_files = task.get("allowed_files")
    if not is_string_list(allowed_files):
        violations.append(f"{manifest}: allowed_files must be a non-empty string array")
        task_files: set[str] = set()
    else:
        task_files = set(allowed_files)
    if not is_string_list(task.get("non_goals")):
        violations.append(f"{manifest}: non_goals must be a non-empty string array")
    if not isinstance(task.get("done_when"), str) or not task["done_when"]:
        violations.append(f"{manifest}: done_when must be a non-empty string")

    batches = task.get("batches", [])
    if not isinstance(batches, list) or not all(
        isinstance(batch, dict) for batch in batches
    ):
        violations.append(f"{manifest}: batches must be an array of tables")
        return violations
    if isinstance(status, str) and status not in {"draft", "approved"} and not batches:
        violations.append(f"{manifest}: current status requires at least one batch")

    batch_ids = [
        batch["id"] for batch in batches if isinstance(batch.get("id"), str)
    ]
    if repeated_batch_ids := duplicates(batch_ids):
        violations.append(
            f"{manifest}: duplicate batch ids: {', '.join(repeated_batch_ids)}"
        )
    declared_batch_ids = set(batch_ids)
    for index, batch in enumerate(batches, start=1):
        batch_id = batch.get("id")
        label = batch_id if isinstance(batch_id, str) and batch_id else str(index)
        if not isinstance(batch_id, str) or not batch_id:
            violations.append(f"{manifest}: batch {index} is missing id")
        items = batch.get("items")
        if not is_string_list(items):
            violations.append(f"{manifest}: batch {label} is missing items")
        elif len(items) > 2:
            violations.append(
                f"{manifest}: batch {label} assigns {len(items)} items; maximum is 2"
            )
        batch_requirements = batch.get("requirements")
        if not is_string_list(batch_requirements):
            violations.append(f"{manifest}: batch {label} is missing requirements")
        else:
            unexpected = sorted(set(batch_requirements) - task_requirements)
            if unexpected:
                violations.append(
                    f"{manifest}: batch {label} requirements outside task scope: "
                    f"{', '.join(unexpected)}"
                )
        batch_files = batch.get("allowed_files")
        if not is_string_list(batch_files):
            violations.append(f"{manifest}: batch {label} is missing allowed_files")
        else:
            unexpected = sorted(set(batch_files) - task_files)
            if unexpected:
                violations.append(
                    f"{manifest}: batch {label} files outside task scope: "
                    f"{', '.join(unexpected)}"
                )
        dependencies = batch.get("dependencies")
        if not is_string_list(dependencies, allow_empty=True):
            violations.append(f"{manifest}: batch {label} is missing dependencies")
        else:
            unknown = sorted(set(dependencies) - declared_batch_ids)
            if unknown:
                violations.append(
                    f"{manifest}: batch {label} has unknown dependencies: "
                    f"{', '.join(unknown)}"
                )
    return violations


def check_work_dir(
    work_dir: Path,
    *,
    changed_files: set[str] | None = None,
) -> list[str]:
    manifest = work_dir / "task.toml"
    if not manifest.is_file():
        return [f"{manifest}: task manifest is missing"]
    try:
        task = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        return [f"{manifest}: invalid TOML: {error}"]

    violations = validate_manifest(task, manifest)
    if violations:
        return violations
    if task["feature_slug"] != work_dir.name:
        violations.append(
            f"{manifest}: feature_slug {task['feature_slug']} does not match work "
            f"directory {work_dir.name}"
        )
    if changed_files is not None:
        unexpected = sorted(changed_files - set(task["allowed_files"]))
        if unexpected:
            violations.append(
                f"{manifest}: changed files outside task scope: {', '.join(unexpected)}"
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
    merge_base = subprocess.run(
        ("git", "merge-base", "HEAD", "main"),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    commands = (
        ("git", "diff", "--no-renames", "--name-only", "-z", f"{merge_base}..HEAD"),
        ("git", "diff", "--no-renames", "--name-only", "-z"),
        ("git", "diff", "--cached", "--no-renames", "--name-only", "-z"),
        ("git", "ls-files", "--others", "--exclude-standard", "-z"),
    )
    changed_files: set[str] = set()
    work_prefix = f"{work_dir.relative_to(repo_root).as_posix()}/"
    for command in commands:
        output = subprocess.run(
            command,
            cwd=repo_root,
            check=True,
            capture_output=True,
        ).stdout
        for value in output.split(b"\0"):
            if not value:
                continue
            path = value.decode("utf-8")
            if not path.startswith(work_prefix):
                changed_files.add(path)
    return changed_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the active agent task")
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    use_git_state = args.work_dir is None
    try:
        work_dir = args.work_dir or resolve_work_dir(args.repo_root)
        changed_files = (
            git_changed_files(args.repo_root, work_dir) if use_git_state else None
        )
    except (subprocess.CalledProcessError, ValueError) as error:
        print(f"Agent work contract: {error}")
        return 1

    violations = check_work_dir(work_dir, changed_files=changed_files)
    if violations:
        for violation in violations:
            print(violation)
        return 1
    print("Agent work contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
