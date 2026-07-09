from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase


class TestProjectBranding(SimpleTestCase):
    def test_project_does_not_mention_old_brand_outside_nginx_and_domain(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        ignored_dirs = {
            ".git",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
        }
        old_brand = "beat" + "vault"
        domain_pattern = re.compile(
            rf"\b(?:www\.|flower\.|[a-z0-9-]+\.)?{old_brand}\.ru\b"
        )
        forbidden_pattern = re.compile(old_brand, flags=re.IGNORECASE)
        offenders: list[str] = []

        for path in repo_root.rglob("*"):
            relative_path = path.relative_to(repo_root)
            if "nginx" in relative_path.parts:
                continue
            if any(part in ignored_dirs for part in relative_path.parts):
                continue
            if path.is_dir():
                continue

            path_for_check = domain_pattern.sub("<domain>", relative_path.as_posix())
            if forbidden_pattern.search(path_for_check):
                offenders.append(relative_path.as_posix())
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            content_for_check = domain_pattern.sub("<domain>", content)
            if forbidden_pattern.search(content_for_check):
                offenders.append(relative_path.as_posix())

        self.assertEqual([], sorted(offenders))
