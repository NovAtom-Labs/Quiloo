from __future__ import annotations

import sys
from pathlib import Path

from scripts.configure_ci_environment import configure_environment


def test_configure_environment_exports_the_active_python(tmp_path: Path) -> None:
    github_environment = tmp_path / "github-env"

    configure_environment(github_environment)

    assert github_environment.read_text() == f"TCAD_DEVSIM_PYTHON={sys.executable}\n"
