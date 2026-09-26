from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_script(name: str) -> ModuleType:
    path = ROOT / "scripts" / f"{name}.py"
    if not path.is_file():
        pytest.fail(f"missing developer command: {path}")
    spec = importlib.util.spec_from_file_location(f"agent_kronig_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_bootstrap_reports_every_missing_or_incompatible_prerequisite() -> None:
    bootstrap = load_script("bootstrap_dev")

    errors = bootstrap.validate_versions(
        python_version=(3, 12, 9),
        git_output=None,
        node_output="v22.18.0",
        pnpm_output="10.15.1",
    )

    assert errors == (
        "Python 3.13 is required; found 3.12.9.",
        "Git is required and was not found on PATH.",
        "Node.js 24 is required; found 22.18.0.",
        "pnpm 11.19 is required; found 10.15.1.",
    )


def test_bootstrap_distinguishes_missing_tools_from_unreadable_versions() -> None:
    bootstrap = load_script("bootstrap_dev")

    missing = bootstrap.validate_versions(
        python_version=(3, 13, 9),
        git_output="git version 2.50.1",
        node_output=None,
        pnpm_output=None,
    )
    unreadable = bootstrap.validate_versions(
        python_version=(3, 13, 9),
        git_output="git version 2.50.1",
        node_output="unexpected",
        pnpm_output="unexpected",
    )

    assert missing == (
        "Node.js 24 is required and was not found on PATH.",
        "pnpm 11.19 is required and was not found on PATH.",
    )
    assert unreadable == (
        "Node.js 24 is required; the installed version could not be read.",
        "pnpm 11.19 is required; the installed version could not be read.",
    )


def test_dependency_fingerprint_changes_for_inputs_or_toolchain(tmp_path: Path) -> None:
    bootstrap = load_script("bootstrap_dev")
    requirements = tmp_path / "requirements.txt"
    project = tmp_path / "pyproject.toml"
    requirements.write_text("fastapi==1\n")
    project.write_text("[project]\nname='example'\n")

    original = bootstrap.dependency_fingerprint(
        (requirements, project), ("python=3.13.9", "platform=Linux")
    )
    repeated = bootstrap.dependency_fingerprint(
        (requirements, project), ("python=3.13.9", "platform=Linux")
    )
    requirements.write_text("fastapi==2\n")
    changed_input = bootstrap.dependency_fingerprint(
        (requirements, project), ("python=3.13.9", "platform=Linux")
    )
    changed_toolchain = bootstrap.dependency_fingerprint(
        (requirements, project), ("python=3.13.9", "platform=Windows")
    )

    assert original == repeated
    assert original != changed_input
    assert changed_input != changed_toolchain


def test_bootstrap_cache_requires_matching_fingerprint_and_existing_outputs(
    tmp_path: Path,
) -> None:
    bootstrap = load_script("bootstrap_dev")
    output = tmp_path / ".venv" / "bin" / "python"
    output.parent.mkdir(parents=True)
    output.write_text("python")
    cache = bootstrap.BootstrapCache(tmp_path / ".tcad-agent-dev" / "bootstrap.json")

    assert cache.is_current("application", "first", (output,)) is False

    cache.record("application", "first")

    assert cache.is_current("application", "first", (output,)) is True
    assert cache.is_current("application", "second", (output,)) is False
    output.unlink()
    assert cache.is_current("application", "first", (output,)) is False
    assert "secret" not in cache.path.read_text().lower()


@pytest.mark.parametrize(
    ("system", "application_parts", "devsim_parts", "electron_parts"),
    [
        (
            "Windows",
            (".venv", "Scripts", "python.exe"),
            ("devsim", ".venv", "Scripts", "python.exe"),
            ("desktop", "node_modules", "electron", "dist", "electron.exe"),
        ),
        (
            "Linux",
            (".venv", "bin", "python"),
            ("devsim", ".venv", "bin", "python"),
            ("desktop", "node_modules", "electron", "dist", "electron"),
        ),
        (
            "Darwin",
            (".venv", "bin", "python"),
            ("devsim", ".venv", "bin", "python"),
            (
                "desktop",
                "node_modules",
                "electron",
                "dist",
                "Electron.app",
                "Contents",
                "MacOS",
                "Electron",
            ),
        ),
    ],
)
def test_development_paths_are_native_and_keep_devsim_separate(
    tmp_path: Path,
    system: str,
    application_parts: tuple[str, ...],
    devsim_parts: tuple[str, ...],
    electron_parts: tuple[str, ...],
) -> None:
    bootstrap = load_script("bootstrap_dev")
    repository = tmp_path / "agent-kronig"

    paths = bootstrap.development_paths(repository, system)

    assert paths.application_python == repository.joinpath(*application_parts)
    assert paths.devsim_python == tmp_path.joinpath(*devsim_parts)
    assert paths.electron == repository.joinpath(*electron_parts)


def test_bootstrap_help_is_available_without_modifying_the_checkout() -> None:
    bootstrap = load_script("bootstrap_dev")

    parser = bootstrap.build_parser()

    assert "Prepare an Agent Kronig source checkout" in parser.description
