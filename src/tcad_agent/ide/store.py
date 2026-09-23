"""SQLite persistence for local IDE workspaces."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from tcad_agent.ide.models import GitSnapshot, RepositorySnapshot, WorkspaceRecord


class IDEStoreError(RuntimeError):
    pass


class WorkspaceNotFoundError(IDEStoreError):
    pass


class SqliteIDEStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    canonical_root TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    git_json TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    last_opened_at TEXT NOT NULL
                )
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
