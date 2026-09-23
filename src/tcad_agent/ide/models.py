"""Strict data contracts for local repository workspaces."""

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, JsonValue

from tcad_agent.domain.models import StrictModel


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


class IDEEvent(StrictModel):
    id: int = Field(ge=1)
    conversation_id: UUID
    kind: str
    payload: dict[str, JsonValue]
    created_at: datetime
