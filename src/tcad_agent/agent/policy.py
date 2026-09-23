"""Workspace-scoped confirmation policy for OpenHands actions."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from openhands.sdk.event import ActionEvent
from openhands.sdk.security import SecurityAnalyzerBase, SecurityRisk
from openhands.tools.file_editor.definition import FileEditorAction
from openhands.tools.task.definition import TaskAction
from openhands.tools.terminal.definition import TerminalAction

_SAFE_COMMANDS = {
    "basename",
    "cargo",
    "cmake",
    "devsim",
    "diff",
    "dirname",
    "find",
    "git",
    "head",
    "ls",
    "make",
    "mypy",
    "pytest",
    "pwd",
    "python",
    "python3",
    "rg",
    "ruff",
    "sed",
    "tail",
    "test",
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
    "mv",
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
_SHELL_CONTROL = re.compile(r"(?:&&|\|\||[;|`]|\$\(|>|<)")


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


def _terminal_risk(workspace: Path, action: TerminalAction) -> SecurityRisk:
    command = action.command.strip()
    if action.is_input:
        return SecurityRisk.MEDIUM
    if not command or _SHELL_CONTROL.search(command):
        return SecurityRisk.HIGH
    try:
        tokens = shlex.split(command)
    except ValueError:
        return SecurityRisk.HIGH
    if not tokens:
        return SecurityRisk.HIGH

    executable = Path(tokens[0]).name
    if executable == "git":
        if len(tokens) < 2 or tokens[1] not in _SAFE_GIT_COMMANDS:
            return SecurityRisk.HIGH
    elif executable in _DANGEROUS_COMMANDS or executable not in _SAFE_COMMANDS:
        return SecurityRisk.HIGH

    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        candidate = Path(token)
        if ".." in candidate.parts:
            return SecurityRisk.HIGH
        if candidate.is_absolute() and not _inside_workspace(workspace, candidate):
            return SecurityRisk.HIGH
        if _credential_path(candidate):
            return SecurityRisk.HIGH
    return SecurityRisk.LOW


def classify_action(workspace: Path, event: ActionEvent) -> SecurityRisk:
    """Classify an action conservatively against a canonical repository root."""

    action = event.action
    if isinstance(action, FileEditorAction):
        target = Path(action.path)
        if not _inside_workspace(workspace, target) or _credential_path(target):
            return SecurityRisk.HIGH
        return SecurityRisk.LOW
    if isinstance(action, TerminalAction):
        return _terminal_risk(workspace, action)
    if isinstance(action, TaskAction):
        return SecurityRisk.MEDIUM
    return SecurityRisk.HIGH


def action_summary(event: ActionEvent) -> str:
    """Return a content-free, bounded description safe for an approval dialog."""

    action = event.action
    if isinstance(action, FileEditorAction):
        target = Path(action.path).expanduser().resolve(strict=False)
        return f"file_editor {action.command}: {target}"
    if isinstance(action, TerminalAction):
        command = " ".join(action.command.split())
        if len(command) > 220:
            command = f"{command[:217]}..."
        return f"terminal: {command}"
    if isinstance(action, TaskAction):
        description = (action.description or "delegated task").strip()
        return f"task {action.subagent_type}: {description[:180]}"
    return f"{event.tool_name}: unrecognized action"


class WorkspaceSecurityAnalyzer(SecurityAnalyzerBase):
    """Apply Quiloo's workspace policy to every OpenHands action."""

    workspace: Path

    def security_risk(self, action: ActionEvent) -> SecurityRisk:
        return classify_action(self.workspace, action)
