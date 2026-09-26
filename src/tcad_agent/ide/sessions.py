"""Single process-scoped agent session for the open repository."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol
from uuid import UUID

from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.models import AgentRunRecord, WorkspaceSessionRecord
from tcad_agent.ide.workspaces import WorkspaceManager


class WorkspaceSessionBusyError(RuntimeError):
    """Raised when a live workspace writer prevents releasing its session."""


class SessionSupervisor(Protocol):
    def active_run_for_workspace(
        self, workspace_id: UUID
    ) -> AgentRunRecord | None: ...

    def stop(self, run_id: UUID) -> AgentRunRecord: ...

    def join(self, run_id: UUID, timeout: float | None = None) -> None: ...


class WorkspaceSessionService:
    """Own the one temporary agent session allowed in a desktop process."""

    def __init__(
        self,
        workspaces: WorkspaceManager,
        conversations: ConversationService,
        runtime_root: Path,
    ) -> None:
        self.workspaces = workspaces
        self.conversations = conversations
        self.store = conversations.store
        self.runtime_root = runtime_root.resolve()
        self._current: WorkspaceSessionRecord | None = None
        self._supervisor: SessionSupervisor | None = None

    def bind_supervisor(self, supervisor: SessionSupervisor) -> None:
        if self._supervisor is not None and self._supervisor is not supervisor:
            raise RuntimeError("workspace session supervisor is already bound")
        self._supervisor = supervisor

    def open(self, workspace_id: UUID) -> WorkspaceSessionRecord:
        self.workspaces.get(workspace_id)
        if self._current is not None:
            if self._current.workspace_id == workspace_id:
                return self._current
            self.release()
        conversation = self.conversations.create(
            workspace_id, "Current workspace session"
        )
        self._current = WorkspaceSessionRecord(
            id=conversation.id,
            workspace_id=conversation.workspace_id,
            created_at=conversation.created_at,
        )
        return self._current

    def current(self) -> WorkspaceSessionRecord | None:
        return self._current

    def release(self) -> None:
        current = self._current
        if current is None:
            return
        if self._active_run(current.workspace_id) is not None:
            raise WorkspaceSessionBusyError(
                "Finish or stop the active agent run before changing repositories."
            )
        self._delete_current(current)

    def shutdown(self) -> None:
        current = self._current
        if current is None:
            return
        active = self._active_run(current.workspace_id)
        if active is not None:
            supervisor = self._require_supervisor()
            supervisor.stop(active.id)
            supervisor.join(active.id, timeout=5)
        self._delete_current(current)

    def _active_run(self, workspace_id: UUID) -> AgentRunRecord | None:
        return self._require_supervisor().active_run_for_workspace(workspace_id)

    def _require_supervisor(self) -> SessionSupervisor:
        if self._supervisor is None:
            raise RuntimeError("workspace session supervisor is not bound")
        return self._supervisor

    def _delete_current(self, current: WorkspaceSessionRecord) -> None:
        self.store.delete_conversation_tree(current.id)
        self._remove_openhands_state(current.id)
        self._current = None

    def _remove_openhands_state(self, session_id: UUID) -> None:
        root = (self.runtime_root / "openhands").resolve()
        for directory_name in (session_id.hex, str(session_id)):
            target = root / directory_name
            if target.is_symlink():
                target.unlink()
                continue
            if not target.exists():
                continue
            resolved = target.resolve()
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise RuntimeError("OpenHands session path escaped runtime storage") from exc
            shutil.rmtree(resolved)
