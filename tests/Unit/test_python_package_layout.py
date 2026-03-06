from __future__ import annotations

from pathlib import Path

import higgs_agent


def test_package_root_exists() -> None:
    assert Path(higgs_agent.__file__).exists()


def test_expected_package_directories_exist() -> None:
    base = Path("src/higgs_agent")
    for child in [
        "application",
        "tickets",
        "routing",
        "providers",
        "guardrails",
        "validation",
        "events",
        "support",
    ]:
        assert (base / child).is_dir()