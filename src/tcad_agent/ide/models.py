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


class WorkspaceTextFile(StrictModel):
    path: str
    content: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)


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


class PermissionCategory(StrEnum):
    EXTERNAL_FILE_ACCESS = "external_file_access"
    SENSITIVE_FILE_ACCESS = "sensitive_file_access"
    PACKAGE_INSTALLATION = "package_installation"
    NETWORK_ACCESS = "network_access"
    REMOTE_EXECUTION = "remote_execution"
    DESTRUCTIVE_COMMAND = "destructive_command"
    GIT_MUTATION = "git_mutation"
    SYSTEM_CHANGE = "system_change"
    COMPLEX_SHELL = "complex_shell"
    UNRECOGNIZED_ACTION = "unrecognized_action"


def is_run_grantable(category: PermissionCategory) -> bool:
    """Return whether a category is narrow enough for run-scoped approval."""

    return category not in {
        PermissionCategory.COMPLEX_SHELL,
        PermissionCategory.UNRECOGNIZED_ACTION,
    }


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
    permission_category: PermissionCategory
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
