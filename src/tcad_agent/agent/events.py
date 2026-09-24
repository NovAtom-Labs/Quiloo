"""Stable, redacted product events derived from OpenHands SDK events."""

from __future__ import annotations

import os
import re
import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import cast
from uuid import UUID

from openhands.sdk.agent.stream_context import (
    StreamProgress,
)
from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    ConversationStateUpdateEvent,
    Event,
    InterruptEvent,
    MessageEvent,
    ObservationEvent,
    PauseEvent,
)
from openhands.sdk.event.conversation_error import ConversationErrorEvent
from openhands.sdk.llm import content_to_str
from openhands.sdk.security import SecurityRisk
from openhands.tools.file_editor.definition import FileEditorAction
from openhands.tools.task.definition import TaskAction, TaskObservation
from openhands.tools.terminal.definition import TerminalAction
from pydantic import JsonValue

from tcad_agent.agent.policy import (
    action_summary,
    approval_explanation,
    classify_action,
    permission_category,
)
from tcad_agent.agent.tools import TcadDomainAction
from tcad_agent.ide.changes import WorkspaceChangeTracker
from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed
from tcad_agent.ide.models import PermissionCategory, WorkspaceBaseline, is_run_grantable
from tcad_agent.ide.store import SqliteIDEStore

MAX_EVENT_TEXT = 16_000
_SECRET_ENV_NAMES = (
    "AWS_BEARER_TOKEN_BEDROCK",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)
_CREDENTIAL_PATTERNS = (
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"(?i)\b(bearer|token|api[_-]?key|secret)\s*[:=]\s*[^\s,;]+"),
)


def structured_action_metadata(event: ActionEvent) -> dict[str, JsonValue]:
    """Return evidence fields derived from typed actions, never summary text."""

    action = event.action
    if isinstance(action, FileEditorAction):
        return {
            "phase": "inspect" if action.command == "view" else "edit",
            "affected_paths": [str(action.path)],
        }
    if isinstance(action, TaskAction):
        return {"phase": "delegate", "subagent": action.subagent_type}
    if isinstance(action, TcadDomainAction):
        phases = {
            "validate_spec": "validate",
            "compile_experiment": "edit",
            "run_experiment": "execute",
            "validate_result": "validate",
            "search_knowledge": "inspect",
            "build_report": "report",
        }
        metadata: dict[str, JsonValue] = {
            "phase": phases.get(action.operation, "unknown")
        }
        if action.operation in {"validate_spec", "validate_result"}:
            metadata["evidence_kind"] = "validation"
        return metadata
    if isinstance(action, TerminalAction):
        try:
            tokens = shlex.split(action.command)
        except ValueError:
            tokens = []
        if len(tokens) >= 4 and tokens[0] == "cd" and tokens[2] == "&&":
            tokens = tokens[3:]
        if tokens and tokens[-1] == "2>&1":
            tokens.pop()
        executable = Path(tokens[0]).name if tokens else ""
        inspection_commands = {
            "cat",
            "diff",
            "find",
            "grep",
            "head",
            "ls",
            "pwd",
            "rg",
            "sed",
            "tail",
            "wc",
        }
        validation_commands = {"mypy", "pytest", "ruff"}
        if executable == "git" and len(tokens) > 1 and tokens[1] in {
            "diff",
            "log",
            "show",
            "status",
        }:
            return {"phase": "inspect"}
        if executable in inspection_commands:
            return {"phase": "inspect"}
        if executable in validation_commands:
            return {
                "phase": "validate",
                "evidence_kind": "validation",
                "validation_scope": "workspace",
            }
        python_executable = re.fullmatch(r"python(?:\d+(?:\.\d+)?)?", executable)
        if python_executable and tokens[1:3] == ["-m", "pytest"]:
            return {
                "phase": "validate",
                "evidence_kind": "validation",
                "validation_scope": "workspace",
            }
        if (
            python_executable
            and len(tokens) > 1
            and Path(tokens[1]).name == "check.py"
        ):
            return {
                "phase": "validate",
                "evidence_kind": "validation",
                "validation_scope": "workspace",
            }
        return {"phase": "execute"}
    phases = {"task_tracker": "plan", "think": "plan", "finish": "report"}
    return {"phase": phases.get(event.tool_name, "unknown")}


def safe_event_text(value: object, secrets: tuple[str, ...] = ()) -> str:
    """Clip and redact a value before it crosses the product event boundary."""

    text = str(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    for pattern in _CREDENTIAL_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    if len(text) > MAX_EVENT_TEXT:
        return f"{text[: MAX_EVENT_TEXT - 20]}...[output clipped]"
    return text


class AgentEventBridge:
    """Convert SDK-specific callbacks to durable, UI-safe product events."""

    def __init__(
        self,
        conversation_id: UUID,
        run_id: UUID,
        store: SqliteIDEStore,
        events: EventFeed,
        conversations: ConversationService,
        *,
        workspace: Path | None = None,
        permission_grants: set[PermissionCategory] | set[str] | None = None,
        secret_values: tuple[str, ...] | None = None,
    ) -> None:
        self.conversation_id = conversation_id
        self.run_id = run_id
        self.store = store
        self.events = events
        self.conversations = conversations
        self.workspace = workspace.resolve() if workspace is not None else None
        raw_grants = permission_grants if permission_grants is not None else set()
        normalized_grants = {PermissionCategory(value) for value in raw_grants}
        raw_grants.clear()
        raw_grants.update(normalized_grants)
        self.permission_grants = cast(set[PermissionCategory], raw_grants)
        self.secret_values = secret_values or tuple(
            value
            for name in _SECRET_ENV_NAMES
            if (value := os.getenv(name)) is not None
        )
        self._approval_actions: set[str] = set()
        self._action_baselines: dict[str, WorkspaceBaseline] = {}
        self._change_tracker = WorkspaceChangeTracker()

    def __call__(self, event: Event) -> None:
        if isinstance(event, ActionEvent):
            self._action(event)
        elif isinstance(event, ObservationEvent):
            self._observation(event)
        elif isinstance(event, MessageEvent):
            self._message(event)
        elif isinstance(event, PauseEvent):
            self.events.append(self.conversation_id, "run_paused", self._base(event))
        elif isinstance(event, InterruptEvent):
            self.events.append(
                self.conversation_id, "run_interrupted", self._base(event)
            )
        elif isinstance(event, AgentErrorEvent | ConversationErrorEvent):
            detail = getattr(event, "error", None) or getattr(event, "detail", "")
            self.events.append(
                self.conversation_id,
                "agent_error",
                {**self._base(event), "detail": self._safe(detail)},
            )
        elif isinstance(event, ConversationStateUpdateEvent):
            self.events.append(
                self.conversation_id,
                "runtime_state_changed",
                {
                    **self._base(event),
                    "key": self._safe(event.key),
                    "value": self._safe(event.value),
                },
            )

    def on_stream(self, frame: StreamProgress) -> None:
        """Discard provider stream deltas because they may contain private reasoning."""

        del frame

    def _action(self, event: ActionEvent) -> None:
        policy_workspace = self.workspace or Path.cwd()
        risk = (
            classify_action(policy_workspace, event)
            if self.workspace is not None
            else event.security_risk
        )
        category = permission_category(policy_workspace, event)
        metadata = structured_action_metadata(event)
        payload: dict[str, JsonValue] = {
            **self._base(event),
            **metadata,
            "action_id": event.id,
            "risk": risk.value,
            "permission_category": category.value,
            "summary": self._safe(action_summary(event)),
            "tool_call_id": event.tool_call_id,
            "tool_name": event.tool_name,
        }
        normalized = self._normalized_action(event)
        if normalized:
            payload["arguments"] = normalized
        if self.workspace is not None and metadata.get("phase") in {
            "edit",
            "execute",
            "delegate",
        }:
            try:
                self._action_baselines[event.id] = self._change_tracker.capture(
                    self.workspace
                )
            except OSError:
                pass
        self.events.append(self.conversation_id, "tool_call_started", payload)
        grant_applies = is_run_grantable(category) and category in self.permission_grants
        if risk is SecurityRisk.HIGH and grant_applies:
            self.events.append(
                self.conversation_id,
                "permission_grant_used",
                {
                    **self._base(event),
                    "action_id": event.id,
                    "permission_category": category.value,
                    "scope": "run",
                    "tool_name": event.tool_name,
                },
            )
        if (
            risk is SecurityRisk.HIGH
            and not grant_applies
            and event.id not in self._approval_actions
        ):
            self._approval_actions.add(event.id)
            self.store.create_approval(
                self.run_id,
                event.id,
                event.tool_name,
                risk.value,
                approval_explanation(policy_workspace, event, category),
                normalized,
                permission_category=category,
            )

    def _observation(self, event: ObservationEvent) -> None:
        payload: dict[str, JsonValue] = {
            **self._base(event),
            "action_id": event.action_id,
            "is_error": event.observation.is_error,
            "output": self._safe(event.observation.text),
            "tool_call_id": event.tool_call_id,
            "tool_name": event.tool_name,
        }
        if isinstance(event.observation, TaskObservation):
            payload.update(
                {
                    "task_id": event.observation.task_id,
                    "subagent": event.observation.subagent,
                    "task_status": event.observation.status,
                }
            )
        baseline = self._action_baselines.pop(event.action_id, None)
        if baseline is not None and self.workspace is not None:
            try:
                action_changes = self._change_tracker.compare(self.workspace, baseline)
            except (OSError, ValueError):
                pass
            else:
                payload["affected_paths"] = [
                    change.path for change in action_changes.files
                ]
        self.events.append(
            self.conversation_id,
            "tool_call_completed",
            payload,
        )

    def _message(self, event: MessageEvent) -> None:
        if event.source != "agent" or event.llm_message.role != "assistant":
            return
        content = self._safe("\n".join(content_to_str(event.llm_message.content))).strip()
        if content:
            self.conversations.add_assistant_message(self.conversation_id, content)

    def _normalized_action(self, event: ActionEvent) -> dict[str, JsonValue]:
        action = event.action
        if isinstance(action, TerminalAction):
            return {"command": self._safe(action.command)}
        if isinstance(action, FileEditorAction):
            return {"command": action.command, "path": self._safe(action.path)}
        if isinstance(action, TaskAction):
            return {
                "description": self._safe(action.description or "delegated task"),
                "subagent_type": action.subagent_type,
            }
        if isinstance(action, TcadDomainAction):
            result: dict[str, JsonValue] = {"operation": action.operation}
            if action.backend is not None:
                result["backend"] = self._safe(action.backend)
            return result
        return {}

    def _safe(self, value: object) -> str:
        return safe_event_text(value, self.secret_values)

    def _base(self, event: Event) -> dict[str, JsonValue]:
        return {"run_id": str(self.run_id), "sdk_event_id": event.id}


def json_mapping(value: Mapping[str, object]) -> dict[str, JsonValue]:
    """Narrow a known JSON-safe mapping for callers constructing product events."""

    return cast(dict[str, JsonValue], dict(value))
