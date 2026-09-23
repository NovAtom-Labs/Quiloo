"""SQLite persistence for local IDE workspaces."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast
from uuid import UUID, uuid4

from pydantic import JsonValue

from tcad_agent.ide.models import (
    ConversationMessage,
    ConversationRecord,
    ConversationState,
    GitSnapshot,
    IDEEvent,
    RepositorySnapshot,
    WorkspaceRecord,
)


class IDEStoreError(RuntimeError):
    pass


class WorkspaceNotFoundError(IDEStoreError):
    pass


class ConversationNotFoundError(IDEStoreError):
    pass


class SqliteIDEStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    canonical_root TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    git_json TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    last_opened_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                    title TEXT NOT NULL,
                    state TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id),
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ide_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id),
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def open_workspace(self, snapshot: RepositorySnapshot) -> WorkspaceRecord:
        now = datetime.now(UTC)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                INSERT INTO workspaces (
                    id,
                    canonical_root,
                    display_name,
                    git_json,
                    revision,
                    created_at,
                    last_opened_at
                ) VALUES (?, ?, ?, ?, 0, ?, ?)
                ON CONFLICT(canonical_root) DO UPDATE SET
                    display_name = excluded.display_name,
                    git_json = excluded.git_json,
                    revision = workspaces.revision + 1,
                    last_opened_at = excluded.last_opened_at
                RETURNING *
                """,
                (
                    str(uuid4()),
                    str(snapshot.root),
                    snapshot.display_name,
                    snapshot.git.model_dump_json(),
                    now.isoformat(),
                    now.isoformat(),
                ),
            ).fetchone()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        if row is None:
            raise IDEStoreError("workspace upsert returned no record")
        return self._workspace(row)

    def get_workspace(self, workspace_id: UUID) -> WorkspaceRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workspaces WHERE id = ?", (str(workspace_id),)
            ).fetchone()
        if row is None:
            raise WorkspaceNotFoundError(f"workspace does not exist: {workspace_id}")
        return self._workspace(row)

    def list_workspaces(self) -> tuple[WorkspaceRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM workspaces
                ORDER BY last_opened_at DESC, id ASC
                """
            ).fetchall()
        return tuple(self._workspace(row) for row in rows)

    def create_conversation(
        self, workspace_id: UUID, title: str
    ) -> ConversationRecord:
        now = datetime.now(UTC)
        conversation_id = uuid4()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(conversation_id),
                    str(workspace_id),
                    title,
                    ConversationState.IDLE.value,
                    0,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        return self.get_conversation(conversation_id)

    def get_conversation(self, conversation_id: UUID) -> ConversationRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversations WHERE id = ?", (str(conversation_id),)
            ).fetchone()
        if row is None:
            raise ConversationNotFoundError(
                f"conversation does not exist: {conversation_id}"
            )
        return self._conversation(row)

    def list_conversations(
        self, workspace_id: UUID
    ) -> tuple[ConversationRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM conversations
                WHERE workspace_id = ?
                ORDER BY updated_at DESC, id ASC
                """,
                (str(workspace_id),),
            ).fetchall()
        return tuple(self._conversation(row) for row in rows)

    def append_message(
        self,
        conversation_id: UUID,
        role: Literal["user", "assistant", "system"],
        content: str,
    ) -> ConversationMessage:
        now = datetime.now(UTC)
        message_id = uuid4()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT id FROM conversations WHERE id = ?", (str(conversation_id),)
            ).fetchone()
            if current is None:
                raise ConversationNotFoundError(
                    f"conversation does not exist: {conversation_id}"
                )
            connection.execute(
                """
                INSERT INTO conversation_messages VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(message_id),
                    str(conversation_id),
                    role,
                    content,
                    now.isoformat(),
                ),
            )
            connection.execute(
                """
                UPDATE conversations
                SET revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (now.isoformat(), str(conversation_id)),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return ConversationMessage(
            id=message_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=now,
        )

    def list_messages(
        self, conversation_id: UUID
    ) -> tuple[ConversationMessage, ...]:
        self.get_conversation(conversation_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (str(conversation_id),),
            ).fetchall()
        return tuple(self._message(row) for row in rows)

    def append_event(
        self,
        conversation_id: UUID,
        kind: str,
        payload: dict[str, JsonValue],
    ) -> IDEEvent:
        self.get_conversation(conversation_id)
        now = datetime.now(UTC)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ide_events (
                    conversation_id, kind, payload_json, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    str(conversation_id),
                    kind,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    now.isoformat(),
                ),
            )
            event_id = cursor.lastrowid
        if event_id is None:
            raise IDEStoreError("event insert returned no identifier")
        return IDEEvent(
            id=event_id,
            conversation_id=conversation_id,
            kind=kind,
            payload=payload,
            created_at=now,
        )

    def list_events_after(
        self, conversation_id: UUID, after_id: int, limit: int
    ) -> tuple[IDEEvent, ...]:
        self.get_conversation(conversation_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM ide_events
                WHERE conversation_id = ? AND id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (str(conversation_id), after_id, limit),
            ).fetchall()
        return tuple(self._event(row) for row in rows)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _workspace(row: sqlite3.Row) -> WorkspaceRecord:
        return WorkspaceRecord(
            id=UUID(row["id"]),
            root=Path(row["canonical_root"]),
            display_name=row["display_name"],
            git=GitSnapshot.model_validate_json(row["git_json"]),
            revision=row["revision"],
            created_at=datetime.fromisoformat(row["created_at"]),
            last_opened_at=datetime.fromisoformat(row["last_opened_at"]),
        )

    @staticmethod
    def _conversation(row: sqlite3.Row) -> ConversationRecord:
        return ConversationRecord(
            id=UUID(row["id"]),
            workspace_id=UUID(row["workspace_id"]),
            title=row["title"],
            state=ConversationState(row["state"]),
            revision=row["revision"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _message(row: sqlite3.Row) -> ConversationMessage:
        role = cast(Literal["user", "assistant", "system"], row["role"])
        return ConversationMessage(
            id=UUID(row["id"]),
            conversation_id=UUID(row["conversation_id"]),
            role=role,
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _event(row: sqlite3.Row) -> IDEEvent:
        payload = cast(dict[str, JsonValue], json.loads(row["payload_json"]))
        return IDEEvent(
            id=row["id"],
            conversation_id=UUID(row["conversation_id"]),
            kind=row["kind"],
            payload=payload,
            created_at=datetime.fromisoformat(row["created_at"]),
        )
