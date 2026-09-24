import json
import shutil
import subprocess
from pathlib import Path

import pytest


def _javascript_runner() -> str | None:
    return shutil.which("node") or next(
        (
            str(path)
            for path in (
                Path(
                    "/System/Library/Frameworks/JavaScriptCore.framework/"
                    "Versions/A/Helpers/jsc"
                ),
                Path("/usr/bin/jsc"),
            )
            if path.is_file()
        ),
        None,
    )


@pytest.mark.skipif(_javascript_runner() is None, reason="No JavaScript runtime installed")
def test_navigation_guard_prevents_stale_browser_updates() -> None:
    project_root = Path(__file__).parents[3]
    source = (
        project_root / "src/tcad_agent/web/static/ide-state.js"
    ).read_text()
    assertions = (
        project_root / "tests/js/ide_navigation_guard.test.js"
    ).read_text()
    completed = subprocess.run(
        [_javascript_runner() or "", "-e", f"{source}\n{assertions}"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(_javascript_runner() is None, reason="No JavaScript runtime installed")
def test_file_viewer_helpers_preserve_scientific_data_and_safe_markdown() -> None:
    project_root = Path(__file__).parents[3]
    source = (
        project_root / "src/tcad_agent/web/static/file-viewer.js"
    ).read_text()
    assertions = (
        project_root / "tests/js/file_viewer.test.js"
    ).read_text()
    completed = subprocess.run(
        [_javascript_runner() or "", "-e", f"{source}\n{assertions}"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(_javascript_runner() is None, reason="No JavaScript runtime installed")
def test_agent_events_reduce_restored_and_live_activity_deterministically() -> None:
    project_root = Path(__file__).parents[3]
    source = (project_root / "src/tcad_agent/web/static/ide-events.js").read_text()
    assertions = (project_root / "tests/js/ide_events.test.js").read_text()
    completed = subprocess.run(
        [_javascript_runner() or "", "-e", f"{source}\n{assertions}"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(_javascript_runner() is None, reason="No JavaScript runtime installed")
def test_agent_markdown_constructs_safe_document_nodes() -> None:
    project_root = Path(__file__).parents[3]
    source = (project_root / "src/tcad_agent/web/static/ide-markdown.js").read_text()
    assertions = (project_root / "tests/js/ide_markdown.test.js").read_text()
    completed = subprocess.run(
        [_javascript_runner() or "", "-e", f"{source}\n{assertions}"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(_javascript_runner() is None, reason="No JavaScript runtime installed")
def test_workbench_layout_preserves_editor_space_and_recovers_preferences() -> None:
    project_root = Path(__file__).parents[3]
    source = (project_root / "src/tcad_agent/web/static/ide-layout.js").read_text()
    assertions = (project_root / "tests/js/ide_layout.test.js").read_text()
    completed = subprocess.run(
        [_javascript_runner() or "", "-e", f"{source}\n{assertions}"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(_javascript_runner() is None, reason="No JavaScript runtime installed")
def test_agent_view_models_group_activity_permissions_and_outcomes() -> None:
    project_root = Path(__file__).parents[3]
    source = (project_root / "src/tcad_agent/web/static/ide-agent.js").read_text()
    assertions = (project_root / "tests/js/ide_agent.test.js").read_text()
    completed = subprocess.run(
        [_javascript_runner() or "", "-e", f"{source}\n{assertions}"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(_javascript_runner() is None, reason="No JavaScript runtime installed")
def test_changes_view_model_handles_text_binary_and_rename_operations() -> None:
    project_root = Path(__file__).parents[3]
    source = (project_root / "src/tcad_agent/web/static/ide-changes.js").read_text()
    assertions = (project_root / "tests/js/ide_changes.test.js").read_text()
    completed = subprocess.run(
        [_javascript_runner() or "", "-e", f"{source}\n{assertions}"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(_javascript_runner() is None, reason="No JavaScript runtime installed")
def test_production_ide_script_parses() -> None:
    project_root = Path(__file__).parents[3]
    source = (project_root / "src/tcad_agent/web/static/ide.js").read_text()
    completed = subprocess.run(
        [_javascript_runner() or "", "-e", f"new Function({json.dumps(source)})"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_production_ide_wires_chat_recovery_file_editing_and_panel_controls() -> None:
    project_root = Path(__file__).parents[3]
    source = (project_root / "src/tcad_agent/web/static/ide.js").read_text()
    permission_source = (
        project_root / "src/tcad_agent/web/static/ide-agent.js"
    ).read_text()

    for required in (
        "refreshCoordinator.request",
        'document.addEventListener("visibilitychange"',
        "setInterval",
        'querySelector("#toggle-agent-panel")',
        'querySelector("#refresh-conversation")',
        'querySelector("#file-viewer-edit")',
        'querySelector("#file-editor")',
        "/files/content",
        "/approve-category",
        "Approve all like this",
        "Technical details",
        "permission_category",
        "technicalArguments",
        "Reversibility:",
        "Run active. Waiting for the next recorded action.",
        "change-validation-link",
        "data-action-id",
        "affectedFilePaths(row, activeWorkspace?.root)",
        "Affected file:",
        "row.validationActionIds.forEach",
        "unlinkedValidationChecks",
        'target.querySelector("summary")?.focus()',
    ):
        assert required in source or required in permission_source

    assert ".slice(0, 12_000)" not in source
    assert "Working in the repository" not in source
    assert 'addEventListener("keydown"' in source


def test_responsive_styles_keep_agent_panel_available_as_a_drawer() -> None:
    project_root = Path(__file__).parents[3]
    source = (project_root / "src/tcad_agent/web/static/ide.css").read_text()

    assert ".toggle-agent-panel" in source
    assert ".agent-panel.is-open" in source
    assert "position: fixed" in source
    assert ".file-editor" in source
    assert ".panel-title > span:first-child" in source
    assert ".panel-title > span:last-child" in source
    assert "text-overflow: ellipsis" in source
    assert ".approval-technical" in source
    assert ".is-approve-category" in source
