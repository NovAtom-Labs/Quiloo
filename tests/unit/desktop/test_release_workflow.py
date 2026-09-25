from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def load_workflow() -> dict[str, object]:
    payload = yaml.safe_load((ROOT / ".github/workflows/desktop-build.yml").read_text())
    assert isinstance(payload, dict)
    return payload


def test_release_workflow_gates_publication_on_every_native_build() -> None:
    workflow = load_workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)

    assert workflow["on"]["push"]["tags"] == ["v*"]
    assert set(jobs) == {"validate", "build", "release"}
    assert jobs["build"]["needs"] == "validate"
    assert jobs["release"]["needs"] == "build"
    assert jobs["release"]["permissions"]["contents"] == "write"
    assert jobs["release"]["if"] == "startsWith(github.ref, 'refs/tags/')"


def test_release_workflow_builds_all_supported_native_targets() -> None:
    workflow = load_workflow()
    rows = workflow["jobs"]["build"]["strategy"]["matrix"]["include"]

    assert {
        (row["runner"], row["platform"], row["arch"])
        for row in rows
    } == {
        ("ubuntu-latest", "linux", "x64"),
        ("windows-latest", "win", "x64"),
        ("macos-15-intel", "mac", "x64"),
        ("macos-15", "mac", "arm64"),
    }


def test_release_workflow_limits_write_permission_and_publishes_a_prerelease() -> None:
    workflow = load_workflow()
    assert workflow["permissions"] == {"contents": "read"}
    release = workflow["jobs"]["release"]
    commands = "\n".join(
        str(step.get("run", "")) for step in release["steps"] if isinstance(step, dict)
    )

    assert "scripts/release_artifacts.py collect" in commands
    assert "gh release create" in commands
    assert commands.index("scripts/release_artifacts.py collect") < commands.index(
        "gh release create"
    )
    assert "--prerelease" in commands
    assert "--verify-tag" in commands
    assert release["steps"][-1]["env"] == {"GH_TOKEN": "${{ secrets.GITHUB_TOKEN }}"}
