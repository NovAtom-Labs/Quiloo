"""Workspace-scoped confirmation policy for OpenHands actions."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from openhands.sdk.event import ActionEvent
from openhands.sdk.security import SecurityAnalyzerBase, SecurityRisk
from openhands.sdk.tool.builtins.finish import FinishAction
from openhands.sdk.tool.builtins.think import ThinkAction
from openhands.tools.file_editor.definition import FileEditorAction
from openhands.tools.task.definition import TaskAction
from openhands.tools.task_tracker.definition import TaskTrackerAction
from openhands.tools.terminal.definition import TerminalAction

from tcad_agent.agent.tools import TcadDomainAction

_SAFE_COMMANDS = {
    "basename",
    "cargo",
    "cat",
    "cmake",
    "cp",
    "devsim",
    "diff",
    "dirname",
    "find",
    "git",
    "grep",
    "head",
    "ls",
    "make",
    "mkdir",
    "mypy",
    "mv",
    "pytest",
    "pwd",
    "python",
    "python3",
    "rg",
    "ruff",
    "sed",
    "tail",
    "test",
    "touch",
    "wc",
}
_SAFE_GIT_COMMANDS = {"branch", "diff", "log", "rev-parse", "show", "status"}
_DANGEROUS_COMMANDS = {
    "apt",
    "apt-get",
    "brew",
    "chmod",
    "chown",
    "curl",
    "dd",
    "dnf",
    "docker",
    "git",  # Git is allowed only through the safe-subcommand branch.
    "kill",
    "killall",
    "nc",
    "npm",
    "npx",
    "pip",
    "pip3",
    "pkill",
    "podman",
    "rm",
    "scp",
    "ssh",
    "sudo",
    "uv",
    "wget",
    "yum",
}
_CREDENTIAL_COMPONENTS = {
    ".aws",
    ".env",
    ".gnupg",
    ".netrc",
    ".ssh",
    "credentials",
    "id_ed25519",
    "id_rsa",
    "secrets",
}
_KNOWN_TOOL_NAMES = {
    "file_editor",
    "finish",
    "task",
    "task_tracker",
    "tcad_domain",
    "terminal",
    "think",
}
_SHELL_CONTROL = re.compile(r"(?:&&|\|\||[;|`$]|>|<)")


def _inside_workspace(workspace: Path, candidate: Path) -> bool:
    root = workspace.expanduser().resolve()
    resolved = candidate.expanduser()
    if not resolved.is_absolute():
        resolved = root / resolved
    resolved = resolved.resolve(strict=False)
    return resolved == root or root in resolved.parents


def _credential_path(path: Path) -> bool:
    lowered = {part.lower() for part in path.parts}
    return bool(lowered & _CREDENTIAL_COMPONENTS)


def _workspace_wrapped_command(workspace: Path, command: str) -> str | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if len(tokens) < 4 or tokens[0] != "cd" or tokens[2] != "&&":
        return None
    if not _inside_workspace(workspace, Path(tokens[1])):
        return None
    body = tokens[3:]
    if body and body[-1] == "2>&1":
        body.pop()
    if not body:
        return None
    return shlex.join(body)


def _terminal_risk(workspace: Path, action: TerminalAction) -> SecurityRisk:
    command = action.command.strip()
    if action.is_input:
        return SecurityRisk.MEDIUM
    if not command:
        return SecurityRisk.HIGH
    if _SHELL_CONTROL.search(command):
        wrapped = _workspace_wrapped_command(workspace, command)
        if wrapped is None:
            return SecurityRisk.HIGH
        command = wrapped
    if _SHELL_CONTROL.search(command):
        return SecurityRisk.HIGH
    try:
        tokens = shlex.split(command)
    except ValueError:
        return SecurityRisk.HIGH
    if not tokens:
        return SecurityRisk.HIGH

    executable = Path(tokens[0]).name
    if executable == "git":
        git_arguments = tokens[1:]
        if git_arguments and git_arguments[0] == "--no-pager":
            git_arguments = git_arguments[1:]
        if not git_arguments or git_arguments[0] not in _SAFE_GIT_COMMANDS:
            return SecurityRisk.HIGH
    elif executable in _DANGEROUS_COMMANDS or executable not in _SAFE_COMMANDS:
        return SecurityRisk.HIGH

    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        candidate = Path(token)
        if ".." in candidate.parts:
            return SecurityRisk.HIGH
        expanded = candidate.expanduser()
        if not _inside_workspace(workspace, expanded):
            return SecurityRisk.HIGH
        if _credential_path(candidate):
            return SecurityRisk.HIGH
    return SecurityRisk.LOW


def classify_action(workspace: Path, event: ActionEvent) -> SecurityRisk:
    """Classify an action conservatively against a canonical repository root."""

    action = event.action
    if action is None and event.tool_name in _KNOWN_TOOL_NAMES:
        return SecurityRisk.LOW
    if isinstance(action, FileEditorAction):
        target = Path(action.path)
        if not _inside_workspace(workspace, target) or _credential_path(target):
            return SecurityRisk.HIGH
        return SecurityRisk.LOW
    if isinstance(action, TerminalAction):
        return _terminal_risk(workspace, action)
    if isinstance(action, TaskTrackerAction):
        return SecurityRisk.LOW
    if isinstance(action, (ThinkAction, FinishAction, TcadDomainAction)):
        return SecurityRisk.LOW
    if isinstance(action, TaskAction):
        return SecurityRisk.MEDIUM
    return SecurityRisk.HIGH


def action_summary(event: ActionEvent) -> str:
    """Return a content-free, bounded description safe for an approval dialog."""

    action = event.action
    if action is None and event.tool_name in _KNOWN_TOOL_NAMES:
        return f"{event.tool_name}: invalid or incomplete action"
    if isinstance(action, FileEditorAction):
        target = Path(action.path).expanduser().resolve(strict=False)
        return f"file_editor {action.command}: {target}"
    if isinstance(action, TerminalAction):
        command = " ".join(action.command.split())
        if len(command) > 220:
            command = f"{command[:217]}..."
        return f"terminal: {command}"
    if isinstance(action, TaskTrackerAction):
        if action.command == "view":
            return "task_tracker: view tasks"
        count = len(action.task_list or ())
        noun = "task" if count == 1 else "tasks"
        return f"task_tracker: update {count} {noun}"
    if isinstance(action, ThinkAction):
        return "think: internal planning"
    if isinstance(action, FinishAction):
        return "finish: complete response"
    if isinstance(action, TcadDomainAction):
        return f"tcad_domain: {action.operation}"
    if isinstance(action, TaskAction):
        description = (action.description or "delegated task").strip()
        return f"task {action.subagent_type}: {description[:180]}"
    return f"{event.tool_name}: unrecognized action"


class WorkspaceSecurityAnalyzer(SecurityAnalyzerBase):
    """Apply Quiloo's workspace policy to every OpenHands action."""

    workspace: Path

    def security_risk(self, action: ActionEvent) -> SecurityRisk:
        return classify_action(self.workspace, action)
