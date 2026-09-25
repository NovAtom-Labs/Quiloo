from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.inspect_desktop_artifacts import inspect_artifacts, main


@pytest.mark.parametrize(
    "relative",
    [
        "backend/_internal/tcad_agent/config.py",
        "mac/Agent Kronig.app/Contents/Resources/app.asar",
    ],
)
def test_scanner_checks_application_owned_content(
    tmp_path: Path, relative: str
) -> None:
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_text("AWS_SECRET_ACCESS_KEY=planted")

    with pytest.raises(ValueError, match="credential pattern"):
        inspect_artifacts(tmp_path)


def test_scanner_checks_zip_members(tmp_path: Path) -> None:
    archive = tmp_path / "Agent-Kronig.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("resources/app/.env.production", "AWS_SECRET_ACCESS_KEY=planted")

    with pytest.raises(ValueError, match="environment file"):
        inspect_artifacts(tmp_path)


def test_scanner_ignores_vendor_environment_templates_without_credentials(
    tmp_path: Path,
) -> None:
    template = tmp_path / "backend" / "_internal" / "vendor_package" / ".env.example"
    template.parent.mkdir(parents=True)
    template.write_text("DOCUMENTED_OPTION=placeholder\n")

    inventory = inspect_artifacts(tmp_path)

    assert inventory[0][0] == "backend/_internal/vendor_package/.env.example"


def test_command_reports_a_sanitized_github_annotation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    planted = tmp_path / "backend" / "agent-kronig-backend"
    planted.parent.mkdir(parents=True)
    planted.write_text("AWS_SECRET_ACCESS_KEY=planted")
    monkeypatch.setattr(sys, "argv", ["inspect_desktop_artifacts.py", str(tmp_path)])

    assert main() == 1

    output = capsys.readouterr().out
    assert output.startswith("::error title=Desktop artifact inspection failed::")
    assert "credential pattern found in artifact" in output
    assert "planted" not in output
