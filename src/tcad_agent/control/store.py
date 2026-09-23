"""SQLite request store with optimistic concurrency and legal transitions."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import JsonValue

from tcad_agent.control.models import RequestRecord, RequestState, ResearchRequest


class RequestStoreError(RuntimeError):
    pass


class RequestNotFoundError(RequestStoreError):
    pass


class ConcurrentTransitionError(RequestStoreError):
    pass


class IllegalTransitionError(RequestStoreError):
    pass


class RequestStore(Protocol):
    def create(self, request: ResearchRequest) -> RequestRecord: ...

    def get(self, request_id: UUID) -> RequestRecord: ...

    def transition(
        self,
        request_id: UUID,
        expected_revision: int,
        target: RequestState,
        data: dict[str, JsonValue],
    ) -> RequestRecord: ...


LEGAL_TRANSITIONS: dict[RequestState, frozenset[RequestState]] = {
    RequestState.REQUESTED: frozenset(
        {RequestState.NEEDS_CLARIFICATION, RequestState.SPEC_DRAFTED, RequestState.FAILED}
    ),
    RequestState.NEEDS_CLARIFICATION: frozenset(
        {RequestState.NEEDS_CLARIFICATION, RequestState.SPEC_DRAFTED, RequestState.FAILED}
    ),
    RequestState.SPEC_DRAFTED: frozenset(
        {RequestState.NEEDS_CLARIFICATION, RequestState.SPEC_VALIDATED, RequestState.FAILED}
    ),
    RequestState.SPEC_VALIDATED: frozenset(
        {RequestState.USER_CONFIRMATION_REQUIRED, RequestState.FAILED}
    ),
    RequestState.USER_CONFIRMATION_REQUIRED: frozenset(
        {RequestState.COMPILED, RequestState.FAILED}
    ),
    RequestState.COMPILED: frozenset({RequestState.RUNNING, RequestState.FAILED}),
    RequestState.RUNNING: frozenset({RequestState.VALIDATING, RequestState.FAILED}),
    RequestState.VALIDATING: frozenset({RequestState.COMPLETED, RequestState.FAILED}),
    RequestState.COMPLETED: frozenset(),
    RequestState.FAILED: frozenset(),
}


class SqliteRequestStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    state TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def create(self, request: ResearchRequest) -> RequestRecord:
        now = datetime.now(UTC)
        record = RequestRecord(
            id=uuid4(),
            request=request,
            state=RequestState.REQUESTED,
            revision=0,
            data={},
            created_at=now,
            updated_at=now,
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(record.id),
                    record.request.prompt,
                    record.state.value,
                    record.revision,
                    "{}",
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )
        return record

    def get(self, request_id: UUID) -> RequestRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM requests WHERE id = ?", (str(request_id),)
            ).fetchone()
        if row is None:
            raise RequestNotFoundError(f"request does not exist: {request_id}")
        return self._record(row)

    def transition(
        self,
        request_id: UUID,
        expected_revision: int,
        target: RequestState,
        data: dict[str, JsonValue],
    ) -> RequestRecord:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM requests WHERE id = ?", (str(request_id),)
            ).fetchone()
            if row is None:
                raise RequestNotFoundError(f"request does not exist: {request_id}")
            current = self._record(row)
            if current.revision != expected_revision:
                raise ConcurrentTransitionError(
                    f"expected revision {expected_revision}, found {current.revision}"
                )
            if target not in LEGAL_TRANSITIONS[current.state]:
                raise IllegalTransitionError(
                    f"illegal request transition {current.state.value} -> {target.value}"
                )
            merged_data = dict(current.data)
            merged_data.update(data)
            updated_at = datetime.now(UTC)
            cursor = connection.execute(
                """
                UPDATE requests
                SET state = ?, revision = ?, data_json = ?, updated_at = ?
                WHERE id = ? AND revision = ?
                """,
                (
                    target.value,
                    current.revision + 1,
                    json.dumps(merged_data, sort_keys=True, separators=(",", ":")),
                    updated_at.isoformat(),
                    str(request_id),
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise ConcurrentTransitionError("request changed during transition")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return self.get(request_id)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _record(row: sqlite3.Row) -> RequestRecord:
        return RequestRecord(
            id=UUID(row["id"]),
            request=ResearchRequest(prompt=row["prompt"]),
            state=RequestState(row["state"]),
            revision=row["revision"],
            data=json.loads(row["data_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
