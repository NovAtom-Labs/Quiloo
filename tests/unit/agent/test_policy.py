from pathlib import Path

import pytest
from openhands.sdk.event import ActionEvent
from openhands.sdk.llm.message import MessageToolCall
from openhands.sdk.security import SecurityRisk
from openhands.sdk.tool import Action
from openhands.sdk.tool.builtins.finish import FinishAction
from openhands.sdk.tool.builtins.think import ThinkAction
from openhands.tools.file_editor.definition import CommandLiteral, FileEditorAction
from openhands.tools.task.definition import TaskAction
from openhands.tools.task_tracker.definition import TaskItem, TaskTrackerAction
from openhands.tools.terminal.definition import TerminalAction

from tcad_agent.agent.policy import (
    WorkspaceSecurityAnalyzer,
    action_summary,
    classify_action,
)
from tcad_agent.agent.tools import TcadDomainAction


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


def action_event(tool_name: str, action: Action | None) -> ActionEvent:
    return ActionEvent(
        thought=[],
        action=action,
        tool_name=tool_name,
        tool_call_id="call-1",
        tool_call=MessageToolCall(
            id="call-1",
            name=tool_name,
            arguments="{}",
            origin="completion",
        ),
        llm_response_id="response-1",
    )


def terminal_event(command: str) -> ActionEvent:
    return action_event("terminal", TerminalAction(command=command))


def file_event(path: str, command: CommandLiteral = "view") -> ActionEvent:
    return action_event(
        "file_editor", FileEditorAction(command=command, path=path)
    )


@pytest.mark.parametrize(
    "command",
    [
        "pytest -q",
        "git diff",
        "rg TODO src",
        "cp tests/test.py.template tests/test.py",
        "mv draft.txt notes/draft.txt",
        "mkdir -p build/results",
        "touch build/results/.keep",
    ],
)
def test_repository_commands_are_low_risk(workspace: Path, command: str) -> None:
    assert classify_action(workspace, terminal_event(command)) is SecurityRisk.LOW


@pytest.mark.parametrize(
    "command",
    [
        "pip install x",
        "git add src",
        "git commit -am x",
        "git push",
        "rm -rf build",
        "cat /etc/passwd",
        "curl https://example.com",
        "sed -n 1p ../secret.txt",
    ],
)
def test_external_or_mutating_commands_require_confirmation(
    workspace: Path, command: str
) -> None:
    assert classify_action(workspace, terminal_event(command)) is SecurityRisk.HIGH


def test_repository_file_actions_are_low_risk(workspace: Path) -> None:
    target = workspace / "src" / "model.py"

    assert classify_action(workspace, file_event(str(target))) is SecurityRisk.LOW
    assert (
        classify_action(workspace, file_event(str(target), command="create"))
        is SecurityRisk.LOW
    )


def test_file_action_outside_workspace_requires_confirmation(workspace: Path) -> None:
    assert (
        classify_action(workspace, file_event("/tmp/external.txt"))
        is SecurityRisk.HIGH
    )


def test_delegated_task_is_medium_risk(workspace: Path) -> None:
    event = action_event(
        "task",
        TaskAction(prompt="Review the device model", subagent_type="code-explorer"),
    )

    assert classify_action(workspace, event) is SecurityRisk.MEDIUM


def test_task_tracker_is_low_risk_workspace_metadata(workspace: Path) -> None:
    event = action_event(
        "task_tracker",
        TaskTrackerAction(
            command="plan",
            task_list=[TaskItem(title="Inspect the repository")],
        ),
    )

    assert classify_action(workspace, event) is SecurityRisk.LOW
    assert action_summary(event) == "task_tracker: update 1 task"


@pytest.mark.parametrize(
    "tool_name,action,summary",
    [
        ("think", ThinkAction(thought="compare fixes"), "think: internal planning"),
        ("finish", FinishAction(message="done"), "finish: complete response"),
        (
            "tcad_domain",
            TcadDomainAction(operation="validate_spec"),
            "tcad_domain: validate_spec",
        ),
    ],
)
def test_builtin_and_tcad_actions_are_low_risk(
    workspace: Path,
    tool_name: str,
    action: Action,
    summary: str,
) -> None:
    event = action_event(tool_name, action)

    assert classify_action(workspace, event) is SecurityRisk.LOW
    assert action_summary(event) == summary


def test_unknown_action_fails_closed(workspace: Path) -> None:
    assert classify_action(workspace, action_event("mystery", None)) is SecurityRisk.HIGH


def test_summary_excludes_file_content_and_clips_commands(workspace: Path) -> None:
    secret = "super-secret-file-content"
    event = action_event(
        "file_editor",
        FileEditorAction(
            command="create",
            path=str(workspace / "result.txt"),
            file_text=secret,
        ),
    )

    assert secret not in action_summary(event)
    assert str((workspace / "result.txt").resolve()) in action_summary(event)
    assert len(action_summary(terminal_event("x" * 1_000))) < 300


def test_security_analyzer_uses_workspace_policy(workspace: Path) -> None:
    analyzer = WorkspaceSecurityAnalyzer(workspace=workspace)

    assert analyzer.security_risk(terminal_event("pytest -q")) is SecurityRisk.LOW
    assert analyzer.security_risk(terminal_event("git push")) is SecurityRisk.HIGH
