"""Testing helpers for fixture-backed validation."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "Fixtures"


def load_json_fixture(relative_path: str) -> dict:
    return json.loads((FIXTURES / relative_path).read_text())


def load_text_fixture(relative_path: str) -> str:
    return (FIXTURES / relative_path).read_text()


def load_markdown_frontmatter(relative_path: str) -> dict:
    content = (FIXTURES / relative_path).read_text()
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"missing frontmatter in fixture: {relative_path}")
    return yaml.safe_load(parts[1])
