"""Persistent activity feed and Server-Sent Event serialization."""

import json
from collections.abc import Iterator
from uuid import UUID

from pydantic import JsonValue

from tcad_agent.ide.models import IDEEvent
from tcad_agent.ide.store import SqliteIDEStore


class EventFeed:
    def __init__(self, store: SqliteIDEStore) -> None:
        self.store = store

    def append(
        self,
        conversation_id: UUID,
        kind: str,
        payload: dict[str, JsonValue],
    ) -> IDEEvent:
        return self.store.append_event(conversation_id, kind, payload)

    def list_after(
        self, conversation_id: UUID, after_id: int, limit: int = 200
    ) -> tuple[IDEEvent, ...]:
        return self.store.list_events_after(conversation_id, after_id, limit)

    def iter_after(
        self, conversation_id: UUID, after_id: int, page_size: int = 200
    ) -> Iterator[IDEEvent]:
        cursor = after_id
        while True:
            page = self.list_after(conversation_id, cursor, page_size)
            if not page:
                return
            yield from page
            cursor = page[-1].id
            if len(page) < page_size:
                return


def format_sse(event: IDEEvent) -> str:
    data = json.dumps(event.model_dump(mode="json"), sort_keys=True)
    return f"id: {event.id}\nevent: {event.kind}\ndata: {data}\n\n"
