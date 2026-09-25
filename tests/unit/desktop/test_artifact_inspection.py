from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.inspect_desktop_artifacts import inspect_artifacts


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
