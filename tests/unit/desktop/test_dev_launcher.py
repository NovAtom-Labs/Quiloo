from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load_launcher() -> ModuleType:
    path = ROOT / "scripts" / "run_desktop_dev.py"
    if not path.is_file():
        pytest.fail(f"missing shared desktop launcher: {path}")
    spec = importlib.util.spec_from_file_location("agent_kronig_dev_launcher", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_launcher_uses_windows_electron_and_isolates_development_data(
    tmp_path: Path,
) -> None:
    launcher = load_launcher()
    repository = tmp_path / "agent-kronig"
    repository.mkdir()
    (repository / ".env").write_text(
        "AWS_REGION_NAME=ap-south-1\nAWS_BEARER_TOKEN_BEDROCK=local-secret\n"
    )

    launch = launcher.resolve_launch(
        repository,
        "Windows",
        {"PATH": "base-path", "AWS_REGION_NAME": "old-region"},
    )

    assert launch.command == repository / "desktop/node_modules/electron/dist/electron.exe"
    assert launch.arguments == (".",)
    assert launch.cwd == repository / "desktop"
    assert launch.environment["AWS_REGION_NAME"] == "ap-south-1"
    assert launch.environment["AWS_BEARER_TOKEN_BEDROCK"] == "local-secret"
    assert launch.environment["TCAD_WORKSPACE"] == str(
        repository / ".tcad-agent-desktop"
    )
    assert launch.environment["OPENHANDS_SUPPRESS_BANNER"] == "1"
    assert "local-secret" not in repr(launch)


def test_launcher_preserves_explicit_workspace_and_rejects_unsupported_system(
    tmp_path: Path,
) -> None:
    launcher = load_launcher()
    repository = tmp_path / "agent-kronig"
    repository.mkdir()

    launch = launcher.resolve_launch(
        repository,
        "Linux",
        {"TCAD_WORKSPACE": "/approved/workspace"},
    )

    assert launch.environment["TCAD_WORKSPACE"] == "/approved/workspace"
    with pytest.raises(launcher.DevelopmentLaunchError, match="Windows, macOS, and Linux"):
        launcher.resolve_launch(repository, "FreeBSD", {})
