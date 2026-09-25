"""Build immutable target-native backend distributions for Electron packaging."""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

RunCommand = Callable[..., subprocess.CompletedProcess[str]]


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_web_assets(project_root: Path, backend_distribution: Path) -> None:
    """Fail when frozen frontend assets differ from the checkout being built."""

    source_web = project_root / "src" / "tcad_agent" / "web"
    if not source_web.is_dir():
        return
    packaged_web = backend_distribution / "_internal" / "tcad_agent" / "web"
    source_files = {
        path.relative_to(source_web)
        for folder in ("static", "templates")
        for path in (source_web / folder).rglob("*")
        if path.is_file()
    }
    packaged_files = {
        path.relative_to(packaged_web)
        for folder in ("static", "templates")
        for path in (packaged_web / folder).rglob("*")
        if path.is_file()
    }
    mismatches = source_files ^ packaged_files
    for relative in source_files & packaged_files:
        if _digest(source_web / relative) != _digest(packaged_web / relative):
            mismatches.add(relative)
    if mismatches:
        summary = ", ".join(str(path) for path in sorted(mismatches)[:5])
        raise RuntimeError(
            "packaged frontend does not match the current checkout: " + summary
        )


def platform_tag(system: str, machine: str) -> str:
    systems = {"Linux": "linux", "Darwin": "mac", "Windows": "win"}
    architectures = {
        "x86_64": "x64",
        "amd64": "x64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    try:
        return f"{systems[system]}-{architectures[machine.lower()]}"
    except KeyError as exc:
        raise ValueError(f"unsupported desktop target: {system} {machine}") from exc


def _pyinstaller_command(
    spec: Path,
    staging_root: Path,
    work_name: str,
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(staging_root / "dist"),
        "--workpath",
        str(staging_root / "work" / work_name),
        str(spec),
    ]


def build_sidecars(
    project_root: Path,
    *,
    output_root: Path,
    staging_root: Path | None = None,
    system: str | None = None,
    machine: str | None = None,
    run_command: RunCommand = subprocess.run,
) -> Path:
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    selected_system = system or platform.system()
    tag = platform_tag(selected_system, machine or platform.machine())
    target = output_root / tag
    if target.exists():
        raise FileExistsError(f"desktop sidecar output already exists: {target}")

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if staging_root is None:
        temporary = tempfile.TemporaryDirectory(prefix="agent-kronig-sidecars-")
        staging_root = Path(temporary.name)
    else:
        staging_root = staging_root.resolve()
        if staging_root.exists():
            raise FileExistsError(f"desktop sidecar staging already exists: {staging_root}")
        staging_root.mkdir(parents=True)

    try:
        specs = project_root / "packaging" / "pyinstaller"
        builds = (
            ("backend", "agent-kronig-backend", specs / "backend.spec"),
            ("devsim", "agent-kronig-devsim", specs / "devsim_runner.spec"),
        )
        for work_name, _, spec in builds:
            run_command(
                _pyinstaller_command(spec, staging_root, work_name),
                cwd=project_root,
                check=True,
                text=True,
            )

        suffix = ".exe" if selected_system == "Windows" else ""
        for _, distribution_name, _ in builds:
            distribution = staging_root / "dist" / distribution_name
            executable = distribution / f"{distribution_name}{suffix}"
            if not executable.is_file():
                raise FileNotFoundError(
                    f"PyInstaller output is missing: {executable}"
                )

        verify_web_assets(
            project_root,
            staging_root / "dist" / "agent-kronig-backend",
        )

        target.mkdir(parents=True)
        for destination, distribution_name, _ in builds:
            shutil.copytree(
                staging_root / "dist" / distribution_name,
                target / destination,
            )
        return target
    finally:
        if temporary is not None:
            temporary.cleanup()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("desktop/resources"),
    )
    parser.add_argument("--staging-root", type=Path)
    arguments = parser.parse_args(argv)
    build_sidecars(
        Path.cwd(),
        output_root=arguments.output_root,
        staging_root=arguments.staging_root,
    )
    return 0
