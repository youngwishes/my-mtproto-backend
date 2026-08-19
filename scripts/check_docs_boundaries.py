#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import unquote


@dataclass(frozen=True, slots=True)
class OwnershipRule:
    owner: str
    pattern: re.Pattern[str]
    message: str


OWNERSHIP_RULES: Final = (
    OwnershipRule(
        owner="docs/DEPLOY.md",
        pattern=re.compile(
            r"\bansible-playbook\b(?:[^\n]*\\\s*\n)*[^\n]*"
            r"\b(?:[\w.-]+/)*deploy\.yml\b"
        ),
        message="release commands belong to docs/DEPLOY.md",
    ),
    OwnershipRule(
        owner="docs/DEPLOY.md",
        pattern=re.compile(
            r"\bansible\b(?:[^\n]*\\\s*\n)*[^\n]*"
            r"inventory/production\.ini"
            r"(?:[^\n]*\\\s*\n)*[^\n]*-a\s+['\"][^'\"]*"
            r"(?:rev-parse\s+HEAD|docker\s+compose\s+ps|nginx\s+-t)"
        ),
        message="release commands belong to docs/DEPLOY.md",
    ),
    OwnershipRule(
        owner="docs/DEPLOY.md",
        pattern=re.compile(
            r"\bcurl\b[^\n]*https://(?:dash\.mtprotokeys\.com|"
            r"flower\.mtprotokeys\.com|beatvault\.ru)"
        ),
        message="release commands belong to docs/DEPLOY.md",
    ),
    OwnershipRule(
        owner="docs/DEPLOY.md",
        pattern=re.compile(r"\bdocker\s+exec\s+nginx\s+nginx\s+-t\b"),
        message="release commands belong to docs/DEPLOY.md",
    ),
    OwnershipRule(
        owner="docs/CONTRACTS.md",
        pattern=re.compile(
            r"\b(?:GET|POST|PUT|PATCH|DELETE)"
            r"(?:/(?:GET|POST|PUT|PATCH|DELETE))*\b[^\n]{0,160}/api(?:/|\b)"
        ),
        message="HTTP contracts belong to docs/CONTRACTS.md",
    ),
    OwnershipRule(
        owner="docs/DEVELOPMENT_WORKFLOW.md",
        pattern=re.compile(
            r"\b(?:scope_revision|task packet|blocking_in_scope|"
            r"scope_change_request|product-agent|product-architect|plan-maker|"
            r"plan-implementer|code-reviewer|product-reviewer|PR_HEAD_SHA|"
            r"write-session)\b|gh\s+pr\s+review\s+--comment|"
            r"--match-head-commit|VERDICT:\s*(?:approved|changes_requested)",
            re.IGNORECASE,
        ),
        message=(
            "delivery workflow mechanics belong to "
            "docs/DEVELOPMENT_WORKFLOW.md"
        ),
    ),
)
APP_MAP_SECTIONS: Final = frozenset(
    {
        "Зона ответственности",
        "Карта компонентов",
        "Зависимости",
        "Границы",
    }
)
MIN_PROSE_DUPLICATE_LENGTH: Final = 160
MIN_CODE_DUPLICATE_LENGTH: Final = 80
MARKDOWN_LINK: Final = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
WIRE_CONTEXT: Final = re.compile(
    r"\b(?:http|api|endpoint|webhook)\b|wire-(?:contract|контракт)|"
    r"\b(?:provider|провайдер)\b.{0,80}"
    r"(?:request|response|payload|запрос|ответ)|"
    r"(?:request|response|payload|запрос|ответ).{0,80}"
    r"\b(?:provider|провайдер)\b",
    re.IGNORECASE,
)
AGENT_REQUIRED_LINKS: Final = (
    "docs/DEVELOPMENT_WORKFLOW.md",
    "docs/BUSINESS.md",
    "docs/ARCHITECTURE.md",
    "docs/CONTRACTS.md",
    "docs/MODELS.md",
    "docs/DEPLOY.md",
    "docs/apps/",
)
WORKFLOW_REQUIRED_LINKS: Final = (
    "BUSINESS.md",
    "ARCHITECTURE.md",
    "CONTRACTS.md",
    "MODELS.md",
    "apps/",
    "DEPLOY.md",
)
APP_REQUIRED_LINKS: Final = {
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
    "VDS.md": ("../ARCHITECTURE.md", "../CONTRACTS.md", "../MODELS.md"),
    "VPN.md": ("../BUSINESS.md", "../CONTRACTS.md", "../MODELS.md"),
}


@dataclass(frozen=True, slots=True)
class Violation:
    path: Path
    line: int
    message: str

    def render(self, *, root: Path) -> str:
        return f"{self.path.relative_to(root)}:{self.line}: {self.message}"


@dataclass(frozen=True, slots=True)
class DocumentationBlock:
    path: Path
    line: int
    text: str


def markdown_files(root: Path) -> list[Path]:
    tracked = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.md",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if tracked.returncode == 0:
        return sorted(root / line for line in tracked.stdout.splitlines() if line)

    excluded_parts = frozenset(
        {
            ".codex",
            ".git",
            ".superpowers",
            ".venv",
            ".venv-integration",
            ".worktrees",
            "node_modules",
        }
    )
    return sorted(
        path
        for path in root.rglob("*.md")
        if not excluded_parts.intersection(path.relative_to(root).parts)
    )


def check_owned_content(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in markdown_files(root):
        text = path.read_text(encoding="utf-8")
        for rule in OWNERSHIP_RULES:
            if path == root / rule.owner:
                continue
            for match in rule.pattern.finditer(text):
                violations.append(
                    Violation(
                        path=path,
                        line=text.count("\n", 0, match.start()) + 1,
                        message=rule.message,
                    )
                )
    return violations


def check_app_map_sections(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    apps_dir = root / "docs" / "apps"
    if not apps_dir.exists():
        return violations
    for path in sorted(apps_dir.glob("*.md")):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            match = re.match(r"^(#{2,6})\s+(.+?)\s*$", line)
            if match and (
                match.group(1) != "##" or match.group(2) not in APP_MAP_SECTIONS
            ):
                violations.append(
                    Violation(
                        path=path,
                        line=line_number,
                        message="app maps may only use canonical map sections",
                    )
                )
    return violations


def check_wire_json_ownership(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    owner = root / "docs" / "CONTRACTS.md"
    for path in markdown_files(root):
        if path == owner:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if not re.match(r"^```json\s*$", line):
                continue
            context = " ".join(lines[max(0, index - 6) : index])
            if WIRE_CONTEXT.search(context):
                violations.append(
                    Violation(
                        path=path,
                        line=index + 1,
                        message="HTTP contracts belong to docs/CONTRACTS.md",
                    )
                )
    return violations


def prose_blocks(path: Path) -> list[DocumentationBlock]:
    blocks: list[DocumentationBlock] = []
    buffer: list[str] = []
    start_line = 0
    in_fence = False

    def flush() -> None:
        nonlocal buffer, start_line
        text = " ".join(" ".join(buffer).split())
        if len(text) >= MIN_PROSE_DUPLICATE_LENGTH:
            blocks.append(DocumentationBlock(path=path, line=start_line, text=text))
        buffer = []
        start_line = 0

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if line.startswith("```"):
            flush()
            in_fence = not in_fence
            continue
        stripped = line.strip()
        if in_fence:
            continue
        if not stripped or stripped.startswith(("#", "|", "- ", "* ", ">")):
            flush()
            continue
        if not buffer:
            start_line = line_number
        buffer.append(stripped)
    flush()
    return blocks


def check_duplicate_prose(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    seen: dict[str, DocumentationBlock] = {}
    for path in markdown_files(root):
        for block in prose_blocks(path):
            previous = seen.get(block.text)
            if previous is None:
                seen[block.text] = block
                continue
            if previous.path == block.path:
                continue
            violations.append(
                Violation(
                    path=block.path,
                    line=block.line,
                    message=(
                        "duplicate prose belongs in one canonical document; "
                        f"first seen in {previous.path.relative_to(root)}:{previous.line}"
                    ),
                )
            )
    return violations


def code_blocks(path: Path) -> list[DocumentationBlock]:
    blocks: list[DocumentationBlock] = []
    buffer: list[str] = []
    start_line = 0
    in_fence = False
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if line.startswith("```"):
            if in_fence:
                text = "\n".join(buffer).strip()
                if len(text) >= MIN_CODE_DUPLICATE_LENGTH:
                    blocks.append(
                        DocumentationBlock(path=path, line=start_line, text=text)
                    )
                buffer = []
                start_line = 0
            else:
                start_line = line_number
            in_fence = not in_fence
            continue
        if in_fence:
            buffer.append(line.rstrip())
    return blocks


def check_duplicate_code(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    seen: dict[str, DocumentationBlock] = {}
    for path in markdown_files(root):
        for block in code_blocks(path):
            previous = seen.get(block.text)
            if previous is None:
                seen[block.text] = block
                continue
            if previous.path == block.path:
                continue
            violations.append(
                Violation(
                    path=block.path,
                    line=block.line,
                    message=(
                        "duplicate code block belongs in one canonical document; "
                        f"first seen in {previous.path.relative_to(root)}:{previous.line}"
                    ),
                )
            )
    return violations


def check_local_links(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in markdown_files(root):
        text = path.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK.finditer(text):
            raw_target = match.group(1).strip().strip("<>")
            if raw_target.startswith(("http://", "https://", "mailto:")):
                continue
            target_without_anchor, _, raw_anchor = raw_target.partition("#")
            if target_without_anchor:
                target = Path(unquote(target_without_anchor))
                resolved = (
                    root / target.relative_to("/")
                    if target.is_absolute()
                    else path.parent / target
                )
            else:
                resolved = path
            line_number = text.count("\n", 0, match.start()) + 1
            if not resolved.exists():
                violations.append(
                    Violation(
                        path=path,
                        line=line_number,
                        message=(
                            "local Markdown link target does not exist: "
                            f"{raw_target}"
                        ),
                    )
                )
                continue
            if raw_anchor and resolved.is_file():
                anchor = unquote(raw_anchor).lower()
                if anchor not in markdown_anchors(resolved):
                    violations.append(
                        Violation(
                            path=path,
                            line=line_number,
                            message=(
                                "local Markdown anchor does not exist: "
                                f"{raw_target}"
                            ),
                        )
                    )
    return violations


def markdown_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    occurrences: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        heading = re.sub(r"[`*_~]", "", match.group(1)).lower()
        heading = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE)
        base = re.sub(r"\s+", "-", heading.strip())
        duplicate_index = occurrences.get(base, 0)
        occurrences[base] = duplicate_index + 1
        anchors.add(base if duplicate_index == 0 else f"{base}-{duplicate_index}")
    return anchors


def check_agent_links(root: Path) -> list[Violation]:
    agents = root / "AGENTS.md"
    if not agents.exists():
        return []
    targets = markdown_link_targets(agents.read_text(encoding="utf-8"))
    return [
        Violation(
            path=agents,
            line=1,
            message=f"AGENTS.md must link to {required}",
        )
        for required in AGENT_REQUIRED_LINKS
        if required not in targets
    ]


def check_workflow_links(root: Path) -> list[Violation]:
    workflow = root / "docs" / "DEVELOPMENT_WORKFLOW.md"
    if not workflow.exists():
        return []
    targets = markdown_link_targets(workflow.read_text(encoding="utf-8"))
    return [
        Violation(
            path=workflow,
            line=1,
            message=f"DEVELOPMENT_WORKFLOW.md must link to {required}",
        )
        for required in WORKFLOW_REQUIRED_LINKS
        if required not in targets
    ]


def check_app_map_links(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    apps_dir = root / "docs" / "apps"
    if not apps_dir.exists():
        return violations
    for path in sorted(apps_dir.glob("*.md")):
        targets = markdown_link_targets(path.read_text(encoding="utf-8"))
        for required in APP_REQUIRED_LINKS.get(path.name, ()):
            if required in targets:
                continue
            violations.append(
                Violation(
                    path=path,
                    line=1,
                    message=f"app map must link to {required}",
                )
            )
    return violations


def markdown_link_targets(text: str) -> set[str]:
    return {
        match.group(1).split("#", maxsplit=1)[0]
        for match in MARKDOWN_LINK.finditer(text)
    }


def check_repository(root: Path) -> list[Violation]:
    return [
        *check_owned_content(root),
        *check_wire_json_ownership(root),
        *check_app_map_sections(root),
        *check_duplicate_prose(root),
        *check_duplicate_code(root),
        *check_local_links(root),
        *check_agent_links(root),
        *check_workflow_links(root),
        *check_app_map_links(root),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check documentation ownership boundaries.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    violations = check_repository(root)
    if not violations:
        print("Documentation boundaries: OK")
        return 0

    print("Documentation boundary violations:")
    for violation in violations:
        print(violation.render(root=root))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
