from __future__ import annotations

import json
from pathlib import Path


def test_protected_surface_policy_remains_review_only() -> None:
    payload = json.loads(Path("config/write-policy.example.json").read_text())
    protected = set(payload["protected_paths"])

    assert ".github/**" in protected
    assert "tickets/**" in protected
    assert "pyproject.toml" in protected
    assert payload["handoff"]["require_human_review_on_protected_path"] is True
    assert payload["handoff"]["require_human_review_on_secret_suspect"] is True
    assert payload["handoff"]["require_human_review_on_policy_violation"] is True