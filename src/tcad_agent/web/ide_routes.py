"""HTTP and event-stream routes for the Linux-local repository IDE."""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse

from tcad_agent.agent.supervisor import AgentRunConflictError, AgentSupervisor
from tcad_agent.ide.changes import WorkspaceChangeTracker
from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed, format_sse
from tcad_agent.ide.models import (
    AgentRunRecord,
    ApprovalRequestRecord,
    ConversationMessage,
    ConversationRecord,
    RunState,
    WorkspaceChangeSet,
    WorkspaceEntry,
    WorkspaceFilePreview,
    WorkspaceRecord,
    WorkspaceTextFile,
)
from tcad_agent.ide.repository import WorkspaceFileConflictError
from tcad_agent.ide.store import IDEStoreError, MessageNotFoundError, SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager
from tcad_agent.web.schemas import (
    CreateConversationRequest,
    CreateMessageRequest,
    DenyAgentApprovalRequest,
    OpenWorkspaceRequest,
    ResolveAgentApprovalRequest,
    SaveWorkspaceFileRequest,
    StartAgentRunRequest,
)


class DirectoryPickerUnavailable(RuntimeError):
    """Raised when the host cannot present a graphical directory chooser."""


class AgentAPIError(RuntimeError):
    """Stable, sanitized error returned by the repository-agent API."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class IDEServices:
    workspaces: WorkspaceManager
    conversations: ConversationService
    events: EventFeed
    changes: WorkspaceChangeTracker = field(default_factory=WorkspaceChangeTracker)
    store: SqliteIDEStore = field(init=False)
    runtime_root: Path = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "store", self.conversations.store)
        object.__setattr__(self, "runtime_root", self.conversations.store.path.parent)


def build_default_ide_services() -> IDEServices:
    runtime_root = Path(
        os.getenv("TCAD_WORKSPACE", str(Path.cwd() / ".tcad-agent"))
    ).resolve()
    store = SqliteIDEStore(runtime_root / "ide.sqlite3")
    events = EventFeed(store)
    return IDEServices(
        workspaces=WorkspaceManager(store),
        conversations=ConversationService(store, events),
        events=events,
    )


def _event_cursor(request: Request, after: int) -> int:
    header = request.headers.get("last-event-id")
    if header is None:
        return after
    try:
        cursor = int(header)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid event cursor") from exc
    if cursor < 0:
        raise HTTPException(status_code=400, detail="invalid event cursor")
    return cursor


def select_directory() -> Path | None:
    """Return a locally selected directory, or None when selection is cancelled."""

    system = platform.system()
    commands: list[list[str]] = []

    if system == "Linux":
        if not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")):
            raise DirectoryPickerUnavailable(
                "A graphical desktop is required for the folder picker. "
                "Enter the repository path manually."
            )
        zenity = shutil.which("zenity")
        kdialog = shutil.which("kdialog")
        if zenity:
            commands.append(
                [
                    zenity,
                    "--file-selection",
                    "--directory",
                    "--title=Open repository folder",
                ]
            )
        if kdialog:
            commands.append([kdialog, "--getexistingdirectory", str(Path.home())])
    elif system == "Darwin":
        if osascript := shutil.which("osascript"):
            commands.append(
                [
                    osascript,
                    "-e",
                    'POSIX path of (choose folder with prompt "Open repository folder")',
                ]
            )
    elif system == "Windows":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if powershell:
            commands.append(
                [
                    powershell,
                    "-NoProfile",
                    "-Command",
                    (
                        "Add-Type -AssemblyName System.Windows.Forms; "
                        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
                        "$dialog.Description = 'Open repository folder'; "
                        "if ($dialog.ShowDialog() -eq 'OK') { $dialog.SelectedPath }"
                    ),
                ]
            )

    if not commands:
        raise DirectoryPickerUnavailable(
            "No native folder picker is available. Enter the repository path manually."
        )

    for command in commands:
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            continue
        if completed.returncode == 1:
            return None
        if completed.returncode != 0:
            continue
        raw_path = completed.stdout.strip()
        if not raw_path:
            return None
        selected = Path(raw_path).expanduser().resolve()
        if selected.is_dir():
            return selected
        raise DirectoryPickerUnavailable(
            "The selected folder is unavailable. Choose another folder or enter its path."
        )

    raise DirectoryPickerUnavailable(
        "The native folder picker could not open. Enter the repository path manually."
    )


def build_ide_router(
    services: IDEServices, supervisor: AgentSupervisor
) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.post("/system/directories/select")
    def select_local_directory(request: Request) -> dict[str, str | None]:
        client_host = request.client.host if request.client else ""
        if client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            raise HTTPException(status_code=403, detail="Folder selection is local only.")
        try:
            selected = select_directory()
        except DirectoryPickerUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"path": str(selected) if selected is not None else None}

    @router.post("/workspaces", status_code=201)
    def open_workspace(payload: OpenWorkspaceRequest) -> WorkspaceRecord:
        return services.workspaces.open(Path(payload.path))

    @router.get("/workspaces")
    def list_workspaces() -> tuple[WorkspaceRecord, ...]:
        return services.workspaces.list()

    @router.get("/workspaces/{workspace_id}")
    def get_workspace(workspace_id: UUID) -> WorkspaceRecord:
        return services.workspaces.get(workspace_id)

    @router.get("/workspaces/{workspace_id}/entries")
    def workspace_entries(
        workspace_id: UUID, path: str = "."
    ) -> tuple[WorkspaceEntry, ...]:
        return services.workspaces.entries(workspace_id, path)

    @router.get("/workspaces/{workspace_id}/files/preview")
    def workspace_file_preview(
        workspace_id: UUID, path: str
    ) -> WorkspaceFilePreview:
        return services.workspaces.preview_file(workspace_id, path)

    @router.get("/workspaces/{workspace_id}/files/raw")
    def workspace_file_raw(
        workspace_id: UUID, path: str, download: bool = False
    ) -> FileResponse:
        preview = services.workspaces.preview_file(workspace_id, path)
        if not download and preview.kind not in {"image", "pdf"}:
            raise HTTPException(
                status_code=415,
                detail="This file type can only be downloaded.",
            )
        target = services.workspaces.file_path(workspace_id, path)
        disposition = "attachment" if download else "inline"
        return FileResponse(
            target,
            media_type=preview.mime_type,
            content_disposition_type=disposition,
            filename=target.name,
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": "sandbox",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get("/workspaces/{workspace_id}/files/content")
    def workspace_file_content(
        workspace_id: UUID, path: str
    ) -> WorkspaceTextFile:
        return services.workspaces.editable_file(workspace_id, path)

    @router.put("/workspaces/{workspace_id}/files/content")
    def save_workspace_file(
        workspace_id: UUID, payload: SaveWorkspaceFileRequest
    ) -> WorkspaceTextFile:
        try:
            return services.workspaces.save_editable_file(
                workspace_id,
                payload.path,
                payload.content,
                payload.expected_sha256,
            )
        except WorkspaceFileConflictError as exc:
            raise AgentAPIError(
                409,
                "workspace_file_conflict",
                "The file changed after it was opened. Refresh before saving.",
            ) from exc

    @router.post("/workspaces/{workspace_id}/conversations", status_code=201)
    def create_conversation(
        workspace_id: UUID, payload: CreateConversationRequest
    ) -> ConversationRecord:
        return services.conversations.create(workspace_id, payload.title)

    @router.get("/workspaces/{workspace_id}/conversations")
    def list_conversations(workspace_id: UUID) -> tuple[ConversationRecord, ...]:
        return services.conversations.list(workspace_id)

    @router.get("/conversations/{conversation_id}")
    def get_conversation(conversation_id: UUID) -> ConversationRecord:
        return services.conversations.get(conversation_id)

    @router.get("/conversations/{conversation_id}/messages")
    def list_messages(
        conversation_id: UUID,
    ) -> tuple[ConversationMessage, ...]:
        return services.conversations.messages(conversation_id)

    @router.post("/conversations/{conversation_id}/messages", status_code=201)
    def create_message(
        conversation_id: UUID, payload: CreateMessageRequest
    ) -> ConversationMessage:
        return services.conversations.add_user_message(conversation_id, payload.content)

    @router.post("/conversations/{conversation_id}/runs", status_code=202)
    def start_agent_run(
        conversation_id: UUID, payload: StartAgentRunRequest
    ) -> AgentRunRecord:
        try:
            message = services.store.get_message(payload.message_id)
        except MessageNotFoundError as exc:
            raise AgentAPIError(
                404, "message_not_found", "The message was not found."
            ) from exc
        if message.conversation_id != conversation_id or message.role != "user":
            raise AgentAPIError(
                400,
                "invalid_run_message",
                "The run must reference a user message in this conversation.",
            )
        try:
            return supervisor.start(
                conversation_id, message.content, persist_message=False
            )
        except AgentRunConflictError as exc:
            raise AgentAPIError(
                409,
                "agent_run_conflict",
                "This workspace already has an active agent run.",
            ) from exc

    @router.get("/conversations/{conversation_id}/runs/active")
    def active_agent_run(conversation_id: UUID) -> AgentRunRecord | None:
        active_states = {
            RunState.QUEUED,
            RunState.RUNNING,
            RunState.WAITING_FOR_APPROVAL,
            RunState.WAITING_FOR_USER,
            RunState.PAUSED,
        }
        runs = services.store.list_runs(conversation_id)
        return next((run for run in reversed(runs) if run.state in active_states), None)

    @router.get("/runs/{run_id}/changes")
    def run_changes(run_id: UUID) -> WorkspaceChangeSet:
        run = services.store.get_run(run_id)
        conversation = services.conversations.get(run.conversation_id)
        workspace = services.workspaces.get(conversation.workspace_id)
        baseline = services.store.get_run_baseline(run_id)
        return services.changes.compare(workspace.root, baseline).model_copy(
            update={"run_id": run_id}
        )

    @router.post("/runs/{run_id}/pause")
    def pause_agent_run(run_id: UUID) -> AgentRunRecord:
        return supervisor.pause(run_id)

    @router.post("/runs/{run_id}/resume")
    def resume_agent_run(run_id: UUID) -> AgentRunRecord:
        return supervisor.resume(run_id)

    @router.post("/runs/{run_id}/stop")
    def stop_agent_run(run_id: UUID) -> AgentRunRecord:
        return supervisor.stop(run_id)

    @router.get("/conversations/{conversation_id}/approvals")
    def pending_approvals(
        conversation_id: UUID,
    ) -> tuple[ApprovalRequestRecord, ...]:
        return services.store.list_pending_approvals(conversation_id)

    def resolve_approval_error(exc: IDEStoreError) -> AgentAPIError:
        detail = str(exc).lower()
        if "cannot be granted" in detail:
            return AgentAPIError(
                400,
                "permission_category_not_grantable",
                "This action is too broad to approve by category. Approve only this action.",
            )
        code = "stale_revision" if "stale" in detail else "approval_not_found"
        status = 409 if code == "stale_revision" else 404
        message = (
            "The approval changed. Refresh before deciding again."
            if code == "stale_revision"
            else "The approval request was not found."
        )
        return AgentAPIError(status, code, message)

    @router.post("/approvals/{approval_id}/approve")
    def approve_agent_action(
        approval_id: UUID, payload: ResolveAgentApprovalRequest
    ) -> AgentRunRecord:
        try:
            return supervisor.approve(approval_id, payload.expected_revision)
        except IDEStoreError as exc:
            raise resolve_approval_error(exc) from exc

    @router.post("/approvals/{approval_id}/approve-category")
    def approve_agent_action_category(
        approval_id: UUID, payload: ResolveAgentApprovalRequest
    ) -> AgentRunRecord:
        try:
            return supervisor.approve_category(
                approval_id, payload.expected_revision
            )
        except IDEStoreError as exc:
            raise resolve_approval_error(exc) from exc

    @router.post("/approvals/{approval_id}/deny")
    def deny_agent_action(
        approval_id: UUID, payload: DenyAgentApprovalRequest
    ) -> AgentRunRecord:
        try:
            return supervisor.deny(
                approval_id, payload.expected_revision, payload.reason
            )
        except IDEStoreError as exc:
            raise resolve_approval_error(exc) from exc

    @router.get("/conversations/{conversation_id}/events")
    async def conversation_events(
        conversation_id: UUID,
        request: Request,
        after: int = Query(default=0, ge=0),
        follow: bool = True,
    ) -> StreamingResponse:
        cursor = _event_cursor(request, after)
        services.conversations.get(conversation_id)

        if not follow:
            rows = services.events.iter_after(conversation_id, cursor)
            return StreamingResponse(
                (format_sse(event) for event in rows),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        async def stream() -> AsyncIterator[str]:
            active_cursor = cursor
            last_output = time.monotonic()
            while not await request.is_disconnected():
                rows = services.events.list_after(conversation_id, active_cursor)
                if rows:
                    for event in rows:
                        active_cursor = event.id
                        last_output = time.monotonic()
                        yield format_sse(event)
                    continue
                if time.monotonic() - last_output >= 15:
                    last_output = time.monotonic()
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.25)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
