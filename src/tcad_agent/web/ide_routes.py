"""HTTP and event-stream routes for the Linux-local repository IDE."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed, format_sse
from tcad_agent.ide.models import (
    ConversationMessage,
    ConversationRecord,
    WorkspaceEntry,
    WorkspaceRecord,
)
from tcad_agent.ide.store import SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager
from tcad_agent.web.schemas import (
    CreateConversationRequest,
    CreateMessageRequest,
    OpenWorkspaceRequest,
)


@dataclass(frozen=True)
class IDEServices:
    workspaces: WorkspaceManager
    conversations: ConversationService
    events: EventFeed


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


def build_ide_router(services: IDEServices) -> APIRouter:
    router = APIRouter(prefix="/api")

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
            rows = services.events.list_after(conversation_id, cursor)
            return StreamingResponse(
                iter(format_sse(event) for event in rows),
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
