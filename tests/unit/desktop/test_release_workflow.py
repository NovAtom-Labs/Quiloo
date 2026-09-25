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
    assert 'Agent Kronig 0.1.0 Alpha 4' in commands
    assert "docs/releases/v0.1.0-alpha.4.md" in commands
    assert release["steps"][-1]["env"] == {"GH_TOKEN": "${{ secrets.GITHUB_TOKEN }}"}


def test_signing_secrets_are_scoped_to_the_steps_and_platforms_that_need_them() -> None:
    workflow = load_workflow()
    build = workflow["jobs"]["build"]
    assert build["env"] == {"OPENHANDS_SUPPRESS_BANNER": "1"}

    steps = {step.get("name"): step for step in build["steps"] if "name" in step}
    installer_env = steps["Build native installers"]["env"]
    assert set(installer_env) == {
        "CSC_LINK",
        "CSC_KEY_PASSWORD",
        "CSC_IDENTITY_AUTO_DISCOVERY",
    }
    assert "matrix.platform == 'mac'" in installer_env["CSC_LINK"]
    assert "matrix.platform == 'win'" in installer_env["CSC_LINK"]
    assert "matrix.platform == 'mac'" in installer_env["CSC_KEY_PASSWORD"]
    assert "matrix.platform == 'win'" in installer_env["CSC_KEY_PASSWORD"]
    assert steps["Sign Linux update artifact"]["env"] == {
        "DESKTOP_LINUX_SIGNING_PRIVATE_KEY": "${{ secrets.DESKTOP_LINUX_SIGNING_PRIVATE_KEY }}"
    }


def test_native_build_fetches_the_exact_public_devsim_knowledge_revision() -> None:
    workflow = load_workflow()
    steps = workflow["jobs"]["build"]["steps"]
    names = [step.get("name") for step in steps]
    fetch = steps[names.index("Fetch pinned DEVSIM knowledge source")]
    build = names.index("Build reviewed knowledge index")

    assert names.index("Fetch pinned DEVSIM knowledge source") < build
    assert "https://github.com/devsim/devsim.git" in fetch["run"]
    assert "43b41ca845184c47e22b72d144db7e7db8509377" in fetch["run"]
    assert "--depth 1" in fetch["run"]
