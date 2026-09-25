from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.release_contract import load_release_identity

ROOT = Path(__file__).resolve().parents[3]


def write_versions(root: Path, python_version: str, desktop_version: str) -> None:
    (root / "desktop").mkdir()
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "agent-kronig"\nversion = "{python_version}"\n'
    )
    (root / "desktop" / "package.json").write_text(
        '{"name":"agent-kronig-desktop","version":"' + desktop_version + '"}'
    )


def test_release_identity_accepts_matching_alpha_versions(tmp_path: Path) -> None:
    write_versions(tmp_path, "0.1.0-alpha.1", "0.1.0-alpha.1")

    identity = load_release_identity(tmp_path, "v0.1.0-alpha.1")

    assert identity.version == "0.1.0-alpha.1"
    assert identity.tag == "v0.1.0-alpha.1"


def test_repository_release_identity_is_alpha_2() -> None:
    identity = load_release_identity(ROOT, "v0.1.0-alpha.2")

    assert identity.version == "0.1.0-alpha.2"
    assert identity.tag == "v0.1.0-alpha.2"


@pytest.mark.parametrize(
    ("python_version", "desktop_version", "tag"),
    [
        ("0.1.0", "0.1.0-alpha.1", "v0.1.0-alpha.1"),
        ("0.1.0-alpha.1", "0.1.0", "v0.1.0-alpha.1"),
        ("0.1.0-alpha.1", "0.1.0-alpha.1", "v0.1.0"),
        ("0.1.0-alpha.1", "0.1.0-alpha.1", "desktop-v0.1.0-alpha.1"),
    ],
)
def test_release_identity_rejects_mismatched_or_nonstandard_versions(
    tmp_path: Path,
    python_version: str,
    desktop_version: str,
    tag: str,
) -> None:
    write_versions(tmp_path, python_version, desktop_version)

    with pytest.raises(ValueError):
        load_release_identity(tmp_path, tag)
