#!/usr/bin/env python3
"""Prepare a fast, repeatable Agent Kronig source-development checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

BOOTSTRAP_SCHEMA = "1"
DEVSIM_VERSION = "2.9.1"


class BootstrapError(RuntimeError):
    """Raised when a development checkout cannot be prepared safely."""


@dataclass(frozen=True)
class DevelopmentPaths:
    repository: Path
    application_python: Path
    devsim_python: Path
    electron: Path
    cache: Path


def development_paths(repository: Path, system: str) -> DevelopmentPaths:
    """Return platform-native paths for isolated development runtimes."""

    repository = repository.resolve()
    electron_parts: tuple[str, ...]
    if system == "Windows":
        python_parts = ("Scripts", "python.exe")
        electron_parts = ("desktop", "node_modules", "electron", "dist", "electron.exe")
    elif system == "Linux":
        python_parts = ("bin", "python")
        electron_parts = ("desktop", "node_modules", "electron", "dist", "electron")
    elif system == "Darwin":
        python_parts = ("bin", "python")
        electron_parts = (
            "desktop",
            "node_modules",
            "electron",
            "dist",
            "Electron.app",
            "Contents",
            "MacOS",
            "Electron",
        )
    else:
        raise BootstrapError("Development setup supports Windows, macOS, and Linux.")
    return DevelopmentPaths(
        repository=repository,
        application_python=repository.joinpath(".venv", *python_parts),
        devsim_python=repository.parent.joinpath("devsim", ".venv", *python_parts),
        electron=repository.joinpath(*electron_parts),
        cache=repository / ".tcad-agent-dev" / "bootstrap.json",
    )


def _version(value: str | None) -> tuple[int, int, int] | None:
    if value is None:
        return None
    match = re.search(r"(?:^|\s|v)(\d+)\.(\d+)(?:\.(\d+))?", value)
    if match is None:
        return None
    return tuple(int(part or 0) for part in match.groups())  # type: ignore[return-value]


def validate_versions(
    *,
    python_version: tuple[int, int, int],
    git_output: str | None,
    node_output: str | None,
    pnpm_output: str | None,
) -> tuple[str, ...]:
    """Return every actionable prerequisite problem in one pass."""

    errors: list[str] = []
    if python_version[:2] != (3, 13):
        errors.append(
            "Python 3.13 is required; found "
            f"{python_version[0]}.{python_version[1]}.{python_version[2]}."
        )
    if git_output is None:
        errors.append("Git is required and was not found on PATH.")
    node_version = _version(node_output)
    if node_output is None:
        errors.append("Node.js 24 is required and was not found on PATH.")
    elif node_version is None:
        errors.append("Node.js 24 is required; the installed version could not be read.")
    elif node_version[0] != 24:
        found = ".".join(map(str, node_version))
        errors.append(f"Node.js 24 is required; found {found}.")
    pnpm_version = _version(pnpm_output)
    if pnpm_output is None:
        errors.append("pnpm 11.19 is required and was not found on PATH.")
    elif pnpm_version is None:
        errors.append("pnpm 11.19 is required; the installed version could not be read.")
    elif pnpm_version[:2] != (11, 19):
        found = ".".join(map(str, pnpm_version))
        errors.append(f"pnpm 11.19 is required; found {found}.")
    return tuple(errors)


def dependency_fingerprint(paths: Sequence[Path], metadata: Sequence[str]) -> str:
    """Hash dependency inputs and toolchain identity for safe setup reuse."""

    digest = hashlib.sha256()
    for item in metadata:
        digest.update(b"metadata\0")
        digest.update(item.encode("utf-8"))
        digest.update(b"\0")
    for path in paths:
        digest.update(b"file\0")
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class BootstrapCache:
    """Small credential-free record of completed dependency stages."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _read(self) -> dict[str, str]:
        try:
            payload = json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        stages = payload.get("stages") if isinstance(payload, dict) else None
        if not isinstance(stages, dict):
            return {}
        return {
            str(name): str(fingerprint)
            for name, fingerprint in stages.items()
            if isinstance(name, str) and isinstance(fingerprint, str)
        }

    def is_current(
        self,
        stage: str,
        fingerprint: str,
        outputs: Sequence[Path],
    ) -> bool:
        return self._read().get(stage) == fingerprint and all(
            output.exists() for output in outputs
        )

    def record(self, stage: str, fingerprint: str) -> None:
        stages = self._read()
        stages[stage] = fingerprint
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"schema": BOOTSTRAP_SCHEMA, "stages": stages},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        temporary.replace(self.path)


def _capture(command: str, *arguments: str) -> str | None:
    executable = shutil.which(command)
    if executable is None:
        return None
    completed = subprocess.run(
        [executable, *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        return None
    return completed.stdout.strip() or completed.stderr.strip()


def _run(command: Sequence[str], repository: Path) -> None:
    subprocess.run(tuple(command), cwd=repository, check=True)


def _prepare_application(paths: DevelopmentPaths) -> None:
    if not paths.application_python.exists():
        _run((sys.executable, "-m", "venv", str(paths.repository / ".venv")), paths.repository)
    python = str(paths.application_python)
    _run((python, "-m", "pip", "install", "--upgrade", "pip"), paths.repository)
    _run(
        (python, "-m", "pip", "install", "-r", str(paths.repository / "requirements.txt")),
        paths.repository,
    )
    _run(
        (python, "-m", "pip", "install", "--editable", str(paths.repository), "--no-deps"),
        paths.repository,
    )


def _prepare_devsim(paths: DevelopmentPaths) -> None:
    environment = paths.devsim_python.parent.parent
    if not paths.devsim_python.exists():
        environment.parent.mkdir(parents=True, exist_ok=True)
        _run((sys.executable, "-m", "venv", str(environment)), paths.repository)
    python = str(paths.devsim_python)
    _run((python, "-m", "pip", "install", "--upgrade", "pip"), paths.repository)
    _run(
        (python, "-m", "pip", "install", f"devsim=={DEVSIM_VERSION}", "numpy"),
        paths.repository,
    )


def _prepare_desktop(paths: DevelopmentPaths, pnpm: str) -> None:
    _run(
        (pnpm, "--dir", str(paths.repository / "desktop"), "install", "--frozen-lockfile"),
        paths.repository,
    )


def _stage(
    *,
    name: str,
    label: str,
    fingerprint: str,
    outputs: Sequence[Path],
    cache: BootstrapCache,
    force: bool,
    prepare: Callable[[], None],
) -> None:
    if not force and cache.is_current(name, fingerprint, outputs):
        print(f"[ready] {label}")
        return
    print(f"[setup] {label}")
    prepare()
    missing = [str(output) for output in outputs if not output.exists()]
    if missing:
        raise BootstrapError(f"{label} did not create: {', '.join(missing)}")
    cache.record(name, fingerprint)
    print(f"[ready] {label}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare an Agent Kronig source checkout for native development."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="reinstall every dependency stage even when its fingerprint is current",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    repository = Path(__file__).resolve().parents[1]
    system = platform.system()
    try:
        paths = development_paths(repository, system)
    except BootstrapError as error:
        print(f"Setup stopped: {error}", file=sys.stderr)
        return 2

    pnpm_command = "pnpm.cmd" if system == "Windows" else "pnpm"
    git_output = _capture("git", "--version")
    node_output = _capture("node", "--version")
    pnpm_output = _capture(pnpm_command, "--version")
    errors = validate_versions(
        python_version=(sys.version_info.major, sys.version_info.minor, sys.version_info.micro),
        git_output=git_output,
        node_output=node_output,
        pnpm_output=pnpm_output,
    )
    if errors:
        print("Development setup cannot continue:", file=sys.stderr)
        for issue in errors:
            print(f"  - {issue}", file=sys.stderr)
        return 2

    assert node_output is not None and pnpm_output is not None
    pnpm = shutil.which(pnpm_command)
    if pnpm is None:
        raise AssertionError("validated pnpm executable disappeared")
    common = (
        f"schema={BOOTSTRAP_SCHEMA}",
        f"python={platform.python_version()}",
        f"system={system}",
    )
    application_fingerprint = dependency_fingerprint(
        (repository / "requirements.txt", repository / "pyproject.toml"),
        (*common, "editable-install=true"),
    )
    devsim_fingerprint = dependency_fingerprint(
        (),
        (*common, f"devsim={DEVSIM_VERSION}"),
    )
    desktop_fingerprint = dependency_fingerprint(
        (repository / "desktop/package.json", repository / "desktop/pnpm-lock.yaml"),
        (*common, f"node={node_output}", f"pnpm={pnpm_output}"),
    )
    cache = BootstrapCache(paths.cache)
    try:
        _stage(
            name="application",
            label="Python application environment",
            fingerprint=application_fingerprint,
            outputs=(paths.application_python,),
            cache=cache,
            force=arguments.force,
            prepare=lambda: _prepare_application(paths),
        )
        _stage(
            name="devsim",
            label="isolated DEVSIM environment",
            fingerprint=devsim_fingerprint,
            outputs=(paths.devsim_python,),
            cache=cache,
            force=arguments.force,
            prepare=lambda: _prepare_devsim(paths),
        )
        _stage(
            name="desktop",
            label="desktop dependencies",
            fingerprint=desktop_fingerprint,
            outputs=(paths.electron,),
            cache=cache,
            force=arguments.force,
            prepare=lambda: _prepare_desktop(paths, pnpm),
        )
    except (BootstrapError, subprocess.CalledProcessError, OSError) as error:
        print(f"Setup stopped: {error}", file=sys.stderr)
        return 1

    launch = (
        ".\\scripts\\run_desktop_dev.ps1"
        if system == "Windows"
        else "scripts/run_desktop_dev.sh"
    )
    print("\nAgent Kronig development setup is ready.")
    print(f"Launch with: {launch}")
    print("Configure Bedrock through Settings after the application opens.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
