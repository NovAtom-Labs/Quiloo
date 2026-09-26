from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.release_artifacts import collect_release_artifacts, stage_platform_artifacts


@pytest.mark.parametrize(
    ("platform", "architecture", "names"),
    [
        (
            "linux",
            "x64",
            (
                "Agent-Kronig-0.1.0-alpha.1-linux-x64.AppImage",
                "Agent-Kronig-0.1.0-alpha.1-linux-x64.deb",
            ),
        ),
        (
            "win",
            "x64",
            (
                "Agent-Kronig-0.1.0-alpha.1-win-x64.exe",
                "Agent-Kronig-0.1.0-alpha.1-win-x64.zip",
            ),
        ),
        (
            "mac",
            "x64",
            (
                "Agent-Kronig-0.1.0-alpha.1-mac-x64.dmg",
                "Agent-Kronig-0.1.0-alpha.1-mac-x64.zip",
            ),
        ),
        (
            "mac",
            "arm64",
            (
                "Agent-Kronig-0.1.0-alpha.1-mac-arm64.dmg",
                "Agent-Kronig-0.1.0-alpha.1-mac-arm64.zip",
            ),
        ),
    ],
)
def test_stage_platform_artifacts_copies_only_required_packages(
    tmp_path: Path,
    platform: str,
    architecture: str,
    names: tuple[str, str],
) -> None:
    source = tmp_path / "dist"
    source.mkdir()
    for name in names:
        (source / name).write_bytes(name.encode())
    (source / "latest.yml").write_text("not published")
    (source / "unpacked").mkdir()
    (source / "unpacked" / "application").write_text("not published")

    staged = stage_platform_artifacts(
        source,
        tmp_path / "stage",
        platform,
        architecture,
    )

    assert tuple(path.name for path in staged) == tuple(sorted(names))
    assert {path.name for path in (tmp_path / "stage").iterdir()} == set(names)


def test_stage_platform_artifacts_includes_optional_linux_signature(
    tmp_path: Path,
) -> None:
    source = tmp_path / "dist"
    source.mkdir()
    names = (
        "Agent-Kronig-0.1.0-alpha.1-linux-x64.AppImage",
        "Agent-Kronig-0.1.0-alpha.1-linux-x64.AppImage.sig",
        "Agent-Kronig-0.1.0-alpha.1-linux-x64.deb",
    )
    for name in names:
        (source / name).write_bytes(name.encode())

    staged = stage_platform_artifacts(source, tmp_path / "stage", "linux", "x64")

    assert tuple(path.name for path in staged) == tuple(sorted(names))


def test_stage_platform_artifacts_normalizes_linux_builder_architectures(
    tmp_path: Path,
) -> None:
    source = tmp_path / "dist"
    source.mkdir()
    for name in (
        "Agent-Kronig-0.1.0-alpha.12-linux-x86_64.AppImage",
        "Agent-Kronig-0.1.0-alpha.12-linux-amd64.deb",
    ):
        (source / name).write_bytes(name.encode())

    staged = stage_platform_artifacts(source, tmp_path / "stage", "linux", "x64")

    assert tuple(path.name for path in staged) == (
        "Agent-Kronig-0.1.0-alpha.12-linux-x64.AppImage",
        "Agent-Kronig-0.1.0-alpha.12-linux-x64.deb",
    )


def test_stage_platform_artifacts_rejects_a_missing_required_package(
    tmp_path: Path,
) -> None:
    source = tmp_path / "dist"
    source.mkdir()
    (source / "Agent-Kronig-0.1.0-alpha.1-win-x64.exe").write_bytes(b"installer")

    with pytest.raises(FileNotFoundError, match="zip"):
        stage_platform_artifacts(source, tmp_path / "stage", "win", "x64")


def test_stage_platform_artifacts_rejects_a_symlinked_package(tmp_path: Path) -> None:
    source = tmp_path / "dist"
    source.mkdir()
    external = tmp_path / "external.zip"
    external.write_bytes(b"external")
    (source / "Agent-Kronig-0.1.0-alpha.1-win-x64.zip").symlink_to(external)
    (source / "Agent-Kronig-0.1.0-alpha.1-win-x64.exe").write_bytes(b"installer")

    with pytest.raises(ValueError, match="symlink"):
        stage_platform_artifacts(source, tmp_path / "stage", "win", "x64")


def test_collect_release_artifacts_rejects_duplicate_filenames(tmp_path: Path) -> None:
    downloads = tmp_path / "downloads"
    for folder in ("linux", "windows"):
        target = downloads / folder
        target.mkdir(parents=True)
        (target / "duplicate.zip").write_bytes(folder.encode())

    with pytest.raises(FileExistsError, match=r"duplicate\.zip"):
        collect_release_artifacts(downloads, tmp_path / "release")


def test_collect_release_artifacts_writes_sorted_checksums(tmp_path: Path) -> None:
    downloads = tmp_path / "downloads"
    first = downloads / "mac-x64" / "zeta.dmg"
    second = downloads / "linux-x64" / "alpha.AppImage"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"zeta")
    second.write_bytes(b"alpha")

    collected = collect_release_artifacts(downloads, tmp_path / "release")

    assert tuple(path.name for path in collected) == (
        "alpha.AppImage",
        "zeta.dmg",
        "SHA256SUMS.txt",
    )
    assert (tmp_path / "release" / "SHA256SUMS.txt").read_text().splitlines() == [
        f"{hashlib.sha256(b'alpha').hexdigest()}  alpha.AppImage",
        f"{hashlib.sha256(b'zeta').hexdigest()}  zeta.dmg",
    ]
