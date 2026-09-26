"""Workspace-scoped confirmation policy for OpenHands actions."""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable
from pathlib import Path

from openhands.sdk.event import ActionEvent
from openhands.sdk.security import SecurityAnalyzerBase, SecurityRisk
from openhands.sdk.tool.builtins.finish import FinishAction
from openhands.sdk.tool.builtins.think import ThinkAction
from openhands.tools.file_editor.definition import FileEditorAction
from openhands.tools.task.definition import TaskAction
from openhands.tools.task_tracker.definition import TaskTrackerAction
from openhands.tools.terminal.definition import TerminalAction
from pydantic import Field

from tcad_agent.agent.tools import TcadDomainAction
from tcad_agent.ide.models import PermissionCategory, is_run_grantable
from tcad_agent.security.paths import is_credential_path

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
_PACKAGE_COMMANDS = {"apt", "apt-get", "brew", "dnf", "npm", "npx", "pip", "pip3", "uv", "yum"}
_NETWORK_COMMANDS = {"curl", "nc", "wget"}
_REMOTE_COMMANDS = {"scp", "ssh"}
_DESTRUCTIVE_COMMANDS = {"dd", "kill", "killall", "pkill", "rm"}
_SYSTEM_COMMANDS = {"chmod", "chown", "docker", "podman", "sudo"}
_WINDOWS_EXECUTABLE = re.compile(r'^(?:"?[A-Za-z]:\\)')


def _command_tokens(command: str) -> list[str]:
    windows_style = bool(_WINDOWS_EXECUTABLE.match(command))
    tokens = shlex.split(command, posix=not windows_style)
    return [token.strip('"') for token in tokens]


def _executable_name(token: str) -> str:
    name = re.split(r"[\\/]", token)[-1].lower()
    return name.removesuffix(".exe")


def _inside_workspace(workspace: Path, candidate: Path) -> bool:
    root = workspace.expanduser().resolve()
    resolved = candidate.expanduser()
    if not resolved.is_absolute():
        resolved = root / resolved
    resolved = resolved.resolve(strict=False)
    return resolved == root or root in resolved.parents


def _workspace_wrapped_command(workspace: Path, command: str) -> str | None:
    try:
        tokens = _command_tokens(command)
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
        tokens = _command_tokens(command)
    except ValueError:
        return SecurityRisk.HIGH
    if not tokens:
        return SecurityRisk.HIGH

    executable = _executable_name(tokens[0])
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
        if is_credential_path(candidate):
            return SecurityRisk.HIGH
    return SecurityRisk.LOW


def classify_action(workspace: Path, event: ActionEvent) -> SecurityRisk:
    """Classify an action conservatively against a canonical repository root."""

    action = event.action
    if action is None and event.tool_name in _KNOWN_TOOL_NAMES:
        return SecurityRisk.LOW
    if isinstance(action, FileEditorAction):
        target = Path(action.path)
        if not _inside_workspace(workspace, target) or is_credential_path(target):
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


def _terminal_permission_category(
    workspace: Path, action: TerminalAction
) -> PermissionCategory:
    command = action.command.strip()
    if _SHELL_CONTROL.search(command):
        wrapped = _workspace_wrapped_command(workspace, command)
        if wrapped is None or _SHELL_CONTROL.search(wrapped):
            return PermissionCategory.COMPLEX_SHELL
        command = wrapped
    try:
        tokens = _command_tokens(command)
    except ValueError:
        return PermissionCategory.COMPLEX_SHELL
    if not tokens:
        return PermissionCategory.UNRECOGNIZED_ACTION

    categories: set[PermissionCategory] = set()
    executable = _executable_name(tokens[0])
    if executable in _PACKAGE_COMMANDS:
        categories.add(PermissionCategory.PACKAGE_INSTALLATION)
    elif executable in _NETWORK_COMMANDS:
        categories.add(PermissionCategory.NETWORK_ACCESS)
    elif executable in _REMOTE_COMMANDS:
        categories.add(PermissionCategory.REMOTE_EXECUTION)
    elif executable in _DESTRUCTIVE_COMMANDS:
        categories.add(PermissionCategory.DESTRUCTIVE_COMMAND)
    elif executable == "git":
        git_arguments = tokens[1:]
        if git_arguments and git_arguments[0] == "--no-pager":
            git_arguments = git_arguments[1:]
        if not git_arguments or git_arguments[0] not in _SAFE_GIT_COMMANDS:
            categories.add(PermissionCategory.GIT_MUTATION)
    elif executable in _SYSTEM_COMMANDS:
        categories.add(PermissionCategory.SYSTEM_CHANGE)
    elif executable not in _SAFE_COMMANDS:
        categories.add(PermissionCategory.UNRECOGNIZED_ACTION)

    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        candidate = Path(token)
        if is_credential_path(candidate):
            categories.add(PermissionCategory.SENSITIVE_FILE_ACCESS)
        if ".." in candidate.parts or not _inside_workspace(workspace, candidate):
            categories.add(PermissionCategory.EXTERNAL_FILE_ACCESS)
    if len(categories) == 1:
        return categories.pop()
    return PermissionCategory.UNRECOGNIZED_ACTION


def permission_category(workspace: Path, event: ActionEvent) -> PermissionCategory:
    """Group a risky action into a deterministic, run-scoped permission."""

    action = event.action
    if isinstance(action, FileEditorAction):
        target = Path(action.path)
        sensitive = is_credential_path(target)
        external = not _inside_workspace(workspace, target)
        if sensitive and external:
            return PermissionCategory.UNRECOGNIZED_ACTION
        if sensitive:
            return PermissionCategory.SENSITIVE_FILE_ACCESS
        if external:
            return PermissionCategory.EXTERNAL_FILE_ACCESS
    if isinstance(action, TerminalAction):
        return _terminal_permission_category(workspace, action)
    return PermissionCategory.UNRECOGNIZED_ACTION


_APPROVAL_EXPLANATIONS = {
    PermissionCategory.EXTERNAL_FILE_ACCESS: (
        "Agent Kronig wants to access a file outside the opened project."
    ),
    PermissionCategory.SENSITIVE_FILE_ACCESS: (
        "Agent Kronig wants to access a file that may contain passwords or credentials."
    ),
    PermissionCategory.PACKAGE_INSTALLATION: (
        "Agent Kronig wants to install or update software on this computer."
    ),
    PermissionCategory.NETWORK_ACCESS: (
        "Agent Kronig wants to connect to the internet or transfer data."
    ),
    PermissionCategory.REMOTE_EXECUTION: (
        "Agent Kronig wants to connect to another computer and run a remote operation."
    ),
    PermissionCategory.DESTRUCTIVE_COMMAND: (
        "Agent Kronig wants to delete files or stop a running process."
    ),
    PermissionCategory.GIT_MUTATION: (
        "Agent Kronig wants to change Git history or send changes to a remote repository."
    ),
    PermissionCategory.SYSTEM_CHANGE: (
        "Agent Kronig wants to change system settings, permissions, or managed services."
    ),
    PermissionCategory.COMPLEX_SHELL: (
        "Agent Kronig wants to run a combined shell command that can perform several operations."
    ),
    PermissionCategory.UNRECOGNIZED_ACTION: (
        "Agent Kronig wants to perform a higher-risk action that it cannot classify more narrowly."
    ),
}


def approval_explanation(
    workspace: Path,
    event: ActionEvent,
    category: PermissionCategory | None = None,
) -> str:
    """Explain an approval in plain language without exposing command contents."""

    selected = category or permission_category(workspace, event)
    return _APPROVAL_EXPLANATIONS[selected]


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
    """Apply Agent Kronig's workspace policy to every OpenHands action."""

    workspace: Path
    permission_grants: set[PermissionCategory] = Field(default_factory=set)
    grant_checker: Callable[[PermissionCategory], bool] | None = Field(
        default=None, exclude=True
    )

    def security_risk(self, action: ActionEvent) -> SecurityRisk:
        risk = classify_action(self.workspace, action)
        if risk is not SecurityRisk.HIGH:
            return risk
        category = permission_category(self.workspace, action)
        if not is_run_grantable(category):
            return risk
        if category in self.permission_grants:
            return SecurityRisk.LOW
        if self.grant_checker is not None and self.grant_checker(category):
            return SecurityRisk.LOW
        return risk
