from __future__ import annotations

import json
from pathlib import Path


def test_write_policy_protects_shared_surfaces() -> None:
    payload = json.loads(Path("config/write-policy.example.json").read_text())
    protected = set(payload["protected_paths"])
    allowed = set(payload["allowed_paths"])
    handoff = payload["handoff"]

    assert ".github/**" in protected
    assert "tickets/**" in protected
    assert "pyproject.toml" in protected
    assert "src/**" in allowed
    assert "tests/**" in allowed
    assert "docs/**" in allowed
    assert payload["limits"]["allow_binary_writes"] is False
    assert all(handoff.values())