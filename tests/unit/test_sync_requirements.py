from pathlib import Path

import pytest

from tcad_agent.dependency_sync import (
    RequirementsSyncError,
    check_direct_requirements,
    ensure_refresh_platform,
    render_direct_requirements,
)

PYPROJECT = """
[project]
dependencies = [
  "fastapi>=0.116,<1",
  "python-dotenv>=1.2,<2",
]

[project.optional-dependencies]
knowledge = ["fastembed>=0.7,<1"]
agent = ["openhands-sdk==1.49.4"]
dev = ["pytest>=8.4,<10"]
"""

LOCK = """
fastapi==0.141.1
fastembed==0.8.1
openhands-sdk==1.49.4
pytest==9.1.1
python-dotenv==1.2.3
starlette==0.52.1
"""


def test_direct_requirements_are_generated_from_pyproject_and_lock() -> None:
    rendered = render_direct_requirements(PYPROJECT, LOCK)

    assert "# Application runtime" in rendered
    assert "fastapi==0.141.1" in rendered
    assert "python-dotenv==1.2.3" in rendered
    assert "# OpenHands repository-agent runtime" in rendered
    assert "openhands-sdk==1.49.4" in rendered
    assert "# Authorized local knowledge retrieval" in rendered
    assert "fastembed==0.8.1" in rendered
    assert "# Verification and dependency maintenance" in rendered
    assert "pytest==9.1.1" in rendered
    assert "starlette" not in rendered


def test_generation_refuses_a_direct_dependency_missing_from_lock() -> None:
    with pytest.raises(RequirementsSyncError, match="python-dotenv"):
        render_direct_requirements(PYPROJECT, LOCK.replace("python-dotenv==1.2.3\n", ""))


def test_check_reports_drift_without_rewriting(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    lock = tmp_path / "requirements.lock"
    direct = tmp_path / "requirements.txt"
    pyproject.write_text(PYPROJECT)
    lock.write_text(LOCK)
    direct.write_text("fastapi==0.141.1\n")

    with pytest.raises(RequirementsSyncError, match="out of date"):
        check_direct_requirements(pyproject, lock, direct)

    assert direct.read_text() == "fastapi==0.141.1\n"


@pytest.mark.parametrize(
    ("system", "version", "message"),
    [
        ("Darwin", (3, 13), "Linux"),
        ("Linux", (3, 12), "Python 3.13"),
    ],
)
def test_full_refresh_requires_linux_python_313(
    system: str,
    version: tuple[int, int],
    message: str,
) -> None:
    with pytest.raises(RequirementsSyncError, match=message):
        ensure_refresh_platform(system, version)
