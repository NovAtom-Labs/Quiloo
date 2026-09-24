"""Strict data contracts for local repository workspaces."""

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, JsonValue

from tcad_agent.domain.models import StrictModel

type WorkspaceFileKind = Literal[
    "text", "markdown", "json", "csv", "tsv", "image", "pdf", "binary"
]


class GitSnapshot(StrictModel):
    available: bool
    root: Path | None = None
    branch: str | None = None
    dirty: bool = False


class RepositorySnapshot(StrictModel):
    root: Path
    display_name: str
    git: GitSnapshot


class WorkspaceEntry(StrictModel):
    path: str
    name: str
    kind: Literal["file", "directory", "symlink"]
    size: int | None = Field(default=None, ge=0)


class WorkspaceFilePreview(StrictModel):
    path: str
    name: str
    kind: WorkspaceFileKind
    mime_type: str
    size: int = Field(ge=0)
    truncated: bool = False
    content: str | None = None


class WorkspaceRecord(StrictModel):
    id: UUID
    root: Path
    display_name: str
    git: GitSnapshot
    revision: int = Field(ge=0)
    created_at: datetime
    last_opened_at: datetime


class ConversationState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    WAITING_FOR_USER = "waiting_for_user"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class ConversationRecord(StrictModel):
    id: UUID
    workspace_id: UUID
    title: str
    state: ConversationState
    revision: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class ConversationMessage(StrictModel):
    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime


class RunState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    WAITING_FOR_USER = "waiting_for_user"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    DENY = "deny"


class AgentRunRecord(StrictModel):
    id: UUID
    conversation_id: UUID
    sdk_conversation_id: UUID
    state: RunState
    revision: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class ApprovalRequestRecord(StrictModel):
    id: UUID
    run_id: UUID
    action_id: str
    tool_name: str
    risk: str
    summary: str
    payload: dict[str, JsonValue]
    decision: ApprovalDecision | None = None
    revision: int = Field(ge=0)
    created_at: datetime
    resolved_at: datetime | None = None


class IDEEvent(StrictModel):
    id: int = Field(ge=1)
    conversation_id: UUID
    kind: str
    payload: dict[str, JsonValue]
    created_at: datetime
