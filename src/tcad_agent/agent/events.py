"""Stable, redacted product events derived from OpenHands SDK events."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import cast
from uuid import UUID

from openhands.sdk.agent.stream_context import (
    StreamAborted,
    StreamDelta,
    StreamProgress,
    StreamStarted,
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

from tcad_agent.agent.policy import action_summary, classify_action
from tcad_agent.agent.tools import TcadDomainAction
from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed
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
        secret_values: tuple[str, ...] | None = None,
    ) -> None:
        self.conversation_id = conversation_id
        self.run_id = run_id
        self.store = store
        self.events = events
        self.conversations = conversations
        self.workspace = workspace.resolve() if workspace is not None else None
        self.secret_values = secret_values or tuple(
            value
            for name in _SECRET_ENV_NAMES
            if (value := os.getenv(name)) is not None
        )
        self._approval_actions: set[str] = set()

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
        """Forward live thinking/text deltas as they generate.

        Shown verbatim in the UI by product decision: the team chose live
        reasoning visibility over the provider's usual guidance to keep
        extended-thinking output hidden from end users. Secret redaction
        still applies; only the "never show raw reasoning" rule is lifted.
        """
        if isinstance(frame, StreamStarted):
            self.events.append(
                self.conversation_id,
                "thinking_started",
                {"item_id": frame.item_id, "attempt": frame.attempt},
            )
        elif isinstance(frame, StreamDelta):
            self.events.append(
                self.conversation_id,
                "thinking_delta",
                {
                    "item_id": frame.item_id,
                    "attempt": frame.attempt,
                    "order": frame.order,
                    "delta_kind": frame.kind,
                    "content": self._safe(frame.content),
                },
            )
        elif isinstance(frame, StreamAborted):
            self.events.append(
                self.conversation_id,
                "thinking_aborted",
                {"item_id": frame.item_id, "reason": frame.reason},
            )

    def _action(self, event: ActionEvent) -> None:
        risk = (
            classify_action(self.workspace, event)
            if self.workspace is not None
            else event.security_risk
        )
        payload: dict[str, JsonValue] = {
            **self._base(event),
            "action_id": event.id,
            "risk": risk.value,
            "summary": self._safe(action_summary(event)),
            "tool_call_id": event.tool_call_id,
            "tool_name": event.tool_name,
        }
        normalized = self._normalized_action(event)
        if normalized:
            payload["arguments"] = normalized
        self.events.append(self.conversation_id, "tool_call_started", payload)
        if (
            risk is SecurityRisk.HIGH
            and event.id not in self._approval_actions
        ):
            self._approval_actions.add(event.id)
            self.store.create_approval(
                self.run_id,
                event.id,
                event.tool_name,
                risk.value,
                self._safe(action_summary(event)),
                normalized,
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
