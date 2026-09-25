import subprocess
import sys
from pathlib import Path

import pytest

from tcad_agent.adapters.registry import resolve_devsim_python

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_devsim_resolution_falls_back_to_the_active_python(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("TCAD_DEVSIM_PYTHON", raising=False)

    assert resolve_devsim_python(tmp_path) == Path(sys.executable).absolute()


def test_devsim_sibling_install_imports_and_reports_version() -> None:
    devsim_python = resolve_devsim_python(PROJECT_ROOT)
    assert devsim_python.is_file()
    completed = subprocess.run(
        [
            str(devsim_python),
            "-c",
            "import devsim; print('DEVSIM_VERSION=' + devsim.__version__)",
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert "DEVSIM_VERSION=2.9.1" in completed.stdout
