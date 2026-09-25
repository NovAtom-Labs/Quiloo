from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tcad_agent.desktop.build_sidecars import build_sidecars, platform_tag


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Linux", "x86_64", "linux-x64"),
        ("Linux", "aarch64", "linux-arm64"),
        ("Darwin", "arm64", "mac-arm64"),
        ("Windows", "AMD64", "win-x64"),
    ],
)
def test_platform_tag_is_target_specific(
    system: str, machine: str, expected: str
) -> None:
    assert platform_tag(system, machine) == expected


def test_build_sidecars_invokes_exact_specs_and_publishes_immutable_layout(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    specs = project / "packaging" / "pyinstaller"
    specs.mkdir(parents=True)
    (specs / "backend.spec").write_text("backend")
    (specs / "devsim_runner.spec").write_text("devsim")
    output_root = project / "desktop" / "resources"
    staging = tmp_path / "staging"
    commands: list[list[str]] = []

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        distribution = staging / "dist" / (
            "agent-kronig-backend"
            if command[-1].endswith("backend.spec")
            else "agent-kronig-devsim"
        )
        distribution.mkdir(parents=True)
        (distribution / distribution.name).write_text("executable")
        return subprocess.CompletedProcess(command, 0)

    target = build_sidecars(
        project,
        output_root=output_root,
        staging_root=staging,
        system="Linux",
        machine="x86_64",
        run_command=runner,
    )

    assert target == output_root / "linux-x64"
    assert (target / "backend" / "agent-kronig-backend").is_file()
    assert (target / "devsim" / "agent-kronig-devsim").is_file()
    assert len(commands) == 2
    for command, spec_name, work_name in zip(
        commands,
        ("backend.spec", "devsim_runner.spec"),
        ("backend", "devsim"),
        strict=True,
    ):
        assert command == [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(staging / "dist"),
            "--workpath",
            str(staging / "work" / work_name),
            str(specs / spec_name),
        ]

    with pytest.raises(FileExistsError, match="already exists"):
        build_sidecars(
            project,
            output_root=output_root,
            staging_root=tmp_path / "second-staging",
            system="Linux",
            machine="x86_64",
            run_command=runner,
        )


def test_build_sidecars_fails_when_pyinstaller_output_is_absent(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    specs = project / "packaging" / "pyinstaller"
    specs.mkdir(parents=True)
    (specs / "backend.spec").write_text("backend")
    (specs / "devsim_runner.spec").write_text("devsim")

    with pytest.raises(FileNotFoundError, match="PyInstaller output is missing"):
        build_sidecars(
            project,
            output_root=project / "desktop" / "resources",
            staging_root=tmp_path / "staging",
            system="Windows",
            machine="AMD64",
            run_command=lambda command, **kwargs: subprocess.CompletedProcess(
                command, 0
            ),
        )


def test_build_sidecars_rejects_frontend_assets_from_a_stale_install(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    specs = project / "packaging" / "pyinstaller"
    specs.mkdir(parents=True)
    (specs / "backend.spec").write_text("backend")
    (specs / "devsim_runner.spec").write_text("devsim")
    source_asset = project / "src" / "tcad_agent" / "web" / "static" / "ide.css"
    source_asset.parent.mkdir(parents=True)
    source_asset.write_text("current checkout")
    staging = tmp_path / "staging"

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        name = (
            "agent-kronig-backend"
            if command[-1].endswith("backend.spec")
            else "agent-kronig-devsim"
        )
        distribution = staging / "dist" / name
        distribution.mkdir(parents=True)
        (distribution / name).write_text("executable")
        if name == "agent-kronig-backend":
            packaged_asset = (
                distribution
                / "_internal"
                / "tcad_agent"
                / "web"
                / "static"
                / "ide.css"
            )
            packaged_asset.parent.mkdir(parents=True)
            packaged_asset.write_text("stale installed package")
        return subprocess.CompletedProcess(command, 0)

    with pytest.raises(RuntimeError, match="does not match the current checkout"):
        build_sidecars(
            project,
            output_root=project / "desktop" / "resources",
            staging_root=staging,
            system="Linux",
            machine="x86_64",
            run_command=runner,
        )
