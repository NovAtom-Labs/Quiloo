import subprocess
from pathlib import Path

DEVSIM_PYTHON = Path("/Users/satyagni/Documents/NovAtom Labs/devsim/.venv/bin/python")


def test_devsim_sibling_install_imports_and_reports_version() -> None:
    assert DEVSIM_PYTHON.is_file()
    completed = subprocess.run(
        [
            str(DEVSIM_PYTHON),
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
