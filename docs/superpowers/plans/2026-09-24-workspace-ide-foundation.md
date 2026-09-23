# Workspace IDE Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working Linux-local IDE slice with safe repository opening, persistent conversations, repository inspection, and resumable live activity streaming while preserving the existing guided TCAD workflow.

**Architecture:** Add an `ide` package containing stable workspace, conversation, and event contracts backed by one local SQLite store. Expose those services through a separate FastAPI router and a new browser IDE shell, while retaining the current simulator request pages under `/simulate` and `/requests/{request_id}/{stage}`. The OpenHands editing and terminal loop will consume these exact contracts in the next vertical slice.

**Tech Stack:** Python 3.13, Pydantic 2, SQLite WAL, FastAPI, Server-Sent Events, vanilla JavaScript, HTML, CSS, Typer, pytest, Ruff, mypy

**Spec:** `docs/superpowers/specs/2026-09-24-linux-local-agent-ide-design.md`

## Global Constraints

- Target Python `>=3.13,<3.14` and preserve all dependency bounds in `pyproject.toml`.
- Bind the local application to `127.0.0.1` by default.
- Support Linux without depending on macOS launchers, AppleScript, or platform-specific file APIs.
- Treat `ExperimentSpec` as the simulator-neutral product contract.
- Keep simulator syntax inside adapter packages.
- Preserve the current request, clarification, approval, execution, validation, evidence, and interactive-result workflow.
- Resolve every workspace path to a canonical absolute directory before persistence or comparison.
- Do not follow a repository symlink outside the workspace during inspection.
- Do not expose model reasoning, credentials, or provider error details through events or HTTP errors.
- Use failing tests before product code and run the complete suite before the final commit.

## Review Focus

- Two spellings or symlinks for the same repository must reopen one persisted workspace rather than create duplicates. Task 2 tests canonical identity.
- A directory entry that is a symlink to an external path must be reported as a symlink and must never be traversed by repository inspection. Task 1 tests this escape case.
- A valid non-Git directory must open normally with `git.available == false`. Task 1 and Task 2 test this path.
- Conversations, messages, and event cursors must survive store reconstruction after a service restart. Task 3 tests reconstruction from the same SQLite file.
- Reconnecting an SSE client with `Last-Event-ID` must deliver only later events and must not duplicate earlier activity. Task 4 tests cursor precedence and ordered delivery.

---

### Task 1: Repository Inspection Primitives

**Files:**
- Create: `src/tcad_agent/ide/__init__.py`
- Create: `src/tcad_agent/ide/models.py`
- Create: `src/tcad_agent/ide/paths.py`
- Create: `src/tcad_agent/ide/repository.py`
- Create: `tests/unit/ide/__init__.py`
- Create: `tests/unit/ide/test_repository.py`

**Interfaces:**
- Consumes: `tcad_agent.domain.models.StrictModel`
- Produces: `canonical_directory(path: Path) -> Path`
- Produces: `resolve_workspace_path(root: Path, relative: str) -> Path`
- Produces: `RepositoryInspector.inspect(root: Path) -> RepositorySnapshot`
- Produces: `RepositoryInspector.entries(root: Path, relative: str = ".") -> tuple[WorkspaceEntry, ...]`
- Produces: `WorkspacePathError`, `RepositorySnapshot`, `GitSnapshot`, and `WorkspaceEntry`

- [ ] **Step 1: Write failing repository-inspection tests**

```python
from pathlib import Path

import pytest

from tcad_agent.ide.paths import WorkspacePathError, canonical_directory
from tcad_agent.ide.repository import RepositoryInspector


def test_inspector_accepts_a_non_git_directory(tmp_path: Path) -> None:
    root = tmp_path / "research"
    root.mkdir()
    (root / "experiment.yaml").write_text("name: reference\n")

    snapshot = RepositoryInspector().inspect(root)

    assert snapshot.root == root.resolve()
    assert snapshot.display_name == "research"
    assert snapshot.git.available is False
    assert [entry.name for entry in RepositoryInspector().entries(root)] == [
        "experiment.yaml"
    ]


def test_entries_report_external_symlink_without_following_it(tmp_path: Path) -> None:
    root = tmp_path / "research"
    outside = tmp_path / "private"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("do not read")
    (root / "external").symlink_to(outside, target_is_directory=True)

    entries = RepositoryInspector().entries(root)

    assert [(item.name, item.kind) for item in entries] == [("external", "symlink")]
    with pytest.raises(WorkspacePathError, match="outside the workspace"):
        RepositoryInspector().entries(root, "external")


def test_canonical_directory_rejects_missing_files_and_plain_files(
    tmp_path: Path,
) -> None:
    regular_file = tmp_path / "file.txt"
    regular_file.write_text("content")

    with pytest.raises(WorkspacePathError, match="does not exist"):
        canonical_directory(tmp_path / "missing")
    with pytest.raises(WorkspacePathError, match="not a directory"):
        canonical_directory(regular_file)
```

- [ ] **Step 2: Run the focused test and confirm the new package is missing**

Run: `.venv/bin/pytest tests/unit/ide/test_repository.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'tcad_agent.ide'`.

- [ ] **Step 3: Add strict repository models**

Create these contracts in `src/tcad_agent/ide/models.py`:

```python
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field

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
```

- [ ] **Step 4: Implement canonical path enforcement**

Implement `src/tcad_agent/ide/paths.py` with these semantics:

```python
from pathlib import Path


class WorkspacePathError(ValueError):
    pass


def canonical_directory(path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.exists():
        raise WorkspacePathError(f"workspace path does not exist: {expanded}")
    resolved = expanded.resolve(strict=True)
    if not resolved.is_dir():
        raise WorkspacePathError(f"workspace path is not a directory: {resolved}")
    return resolved


def resolve_workspace_path(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute():
        raise WorkspacePathError("workspace-relative path must not be absolute")
    canonical_root = canonical_directory(root)
    candidate = canonical_root if relative in {"", "."} else canonical_root / relative
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(canonical_root):
        raise WorkspacePathError("path resolves outside the workspace")
    return resolved
```

- [ ] **Step 5: Implement bounded Git and directory inspection**

In `src/tcad_agent/ide/repository.py`, use `git rev-parse --show-toplevel`,
`git branch --show-current`, and `git status --porcelain=v1`. If `git rev-parse` exits nonzero or
Git is absent, return `GitSnapshot(available=False)`. Directory listing must classify symlinks
before files or directories, never recurse implicitly, return workspace-relative POSIX paths,
and sort directories first, then files and symlinks by case-folded name. Use this implementation:

```python
import subprocess
from pathlib import Path

from tcad_agent.ide.models import GitSnapshot, RepositorySnapshot, WorkspaceEntry
from tcad_agent.ide.paths import (
    WorkspacePathError,
    canonical_directory,
    resolve_workspace_path,
)


class RepositoryInspector:
    def inspect(self, root: Path) -> RepositorySnapshot:
        canonical_root = canonical_directory(root)
        return RepositorySnapshot(
            root=canonical_root,
            display_name=canonical_root.name,
            git=self._git_snapshot(canonical_root),
        )

    def entries(
        self, root: Path, relative: str = "."
    ) -> tuple[WorkspaceEntry, ...]:
        canonical_root = canonical_directory(root)
        target = resolve_workspace_path(canonical_root, relative)
        if not target.is_dir():
            raise WorkspacePathError("workspace entry is not a directory")
        rows = []
        for child in target.iterdir():
            child_relative = child.relative_to(canonical_root).as_posix()
            if child.is_symlink():
                rows.append(
                    WorkspaceEntry(
                        path=child_relative,
                        name=child.name,
                        kind="symlink",
                    )
                )
            elif child.is_dir():
                rows.append(
                    WorkspaceEntry(
                        path=child_relative,
                        name=child.name,
                        kind="directory",
                    )
                )
            elif child.is_file():
                rows.append(
                    WorkspaceEntry(
                        path=child_relative,
                        name=child.name,
                        kind="file",
                        size=child.stat().st_size,
                    )
                )
        order = {"directory": 0, "file": 1, "symlink": 2}
        return tuple(sorted(rows, key=lambda row: (order[row.kind], row.name.casefold())))

    @staticmethod
    def _git_snapshot(root: Path) -> GitSnapshot:
        def run(*arguments: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", *arguments],
                shell=False,
                cwd=root,
                timeout=2,
                check=False,
                capture_output=True,
                text=True,
            )

        try:
            git_root = run("rev-parse", "--show-toplevel")
            if git_root.returncode != 0:
                return GitSnapshot(available=False)
            branch = run("branch", "--show-current")
            status = run("status", "--porcelain=v1")
        except (OSError, subprocess.TimeoutExpired):
            return GitSnapshot(available=False)
        return GitSnapshot(
            available=True,
            root=Path(git_root.stdout.strip()).resolve(),
            branch=branch.stdout.strip() or None,
            dirty=bool(status.stdout.strip()),
        )
```

- [ ] **Step 6: Run the focused tests**

Run: `.venv/bin/pytest tests/unit/ide/test_repository.py -v`

Expected: all repository-inspection tests pass.

- [ ] **Step 7: Run static checks for the new package**

Run: `.venv/bin/ruff check src/tcad_agent/ide tests/unit/ide && .venv/bin/mypy src/tcad_agent/ide`

Expected: both commands exit zero.

- [ ] **Step 8: Commit the repository-inspection boundary**

```bash
git add src/tcad_agent/ide tests/unit/ide
git commit -m "feat: add safe repository inspection"
```

### Task 2: Persistent Workspace Registry

**Files:**
- Create: `src/tcad_agent/ide/store.py`
- Create: `src/tcad_agent/ide/workspaces.py`
- Create: `tests/unit/ide/test_store.py`
- Create: `tests/unit/ide/test_workspaces.py`

**Interfaces:**
- Consumes: `RepositoryInspector.inspect()` and `RepositoryInspector.entries()` from Task 1
- Produces: `SqliteIDEStore(path: Path)`
- Produces: `SqliteIDEStore.open_workspace(snapshot: RepositorySnapshot) -> WorkspaceRecord`
- Produces: `WorkspaceManager.open(path: Path) -> WorkspaceRecord`
- Produces: `WorkspaceManager.list() -> tuple[WorkspaceRecord, ...]`
- Produces: `WorkspaceManager.get(workspace_id: UUID) -> WorkspaceRecord`
- Produces: `WorkspaceManager.entries(workspace_id: UUID, relative: str) -> tuple[WorkspaceEntry, ...]`

- [ ] **Step 1: Write failing persistence and canonical-identity tests**

```python
from pathlib import Path

from tcad_agent.ide.store import SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager


def test_reopening_same_canonical_directory_reuses_workspace(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    alias = tmp_path / "repo-alias"
    alias.symlink_to(root, target_is_directory=True)
    manager = WorkspaceManager(SqliteIDEStore(tmp_path / "ide.sqlite3"))

    first = manager.open(root)
    second = manager.open(alias)

    assert second.id == first.id
    assert second.revision == first.revision + 1
    assert manager.list() == (second,)


def test_workspace_survives_store_reconstruction(tmp_path: Path) -> None:
    root = tmp_path / "plain-directory"
    root.mkdir()
    database = tmp_path / "ide.sqlite3"
    created = WorkspaceManager(SqliteIDEStore(database)).open(root)

    reopened = WorkspaceManager(SqliteIDEStore(database)).get(created.id)

    assert reopened.root == root.resolve()
    assert reopened.git.available is False
```

- [ ] **Step 2: Run tests and confirm store modules are missing**

Run: `.venv/bin/pytest tests/unit/ide/test_store.py tests/unit/ide/test_workspaces.py -v`

Expected: collection fails because `tcad_agent.ide.store` and `tcad_agent.ide.workspaces` do not
exist.

- [ ] **Step 3: Implement the SQLite workspace table and record mapping**

`SqliteIDEStore.__init__` must create its parent directory, enable WAL and foreign keys, and run:

```sql
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    canonical_root TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    git_json TEXT NOT NULL,
    revision INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    last_opened_at TEXT NOT NULL
)
```

Use an explicit transaction and this upsert statement inside `open_workspace`:

```sql
INSERT INTO workspaces (
    id, canonical_root, display_name, git_json, revision, created_at, last_opened_at
) VALUES (?, ?, ?, ?, 0, ?, ?)
ON CONFLICT(canonical_root) DO UPDATE SET
    display_name = excluded.display_name,
    git_json = excluded.git_json,
    revision = workspaces.revision + 1,
    last_opened_at = excluded.last_opened_at
RETURNING *
```

Implement `__init__(path: Path)`, `open_workspace(snapshot: RepositorySnapshot)`,
`get_workspace(workspace_id: UUID)`, and `list_workspaces()` as public methods. Map rows through a
single private `_workspace(row: sqlite3.Row) -> WorkspaceRecord` function. `open_workspace` must
use the canonical root as the unique identity. On conflict it updates the display name, Git
snapshot, last-opened time, and revision without changing the workspace UUID or creation time.

- [ ] **Step 4: Implement `WorkspaceManager`**

Create `src/tcad_agent/ide/workspaces.py`:

```python
class WorkspaceManager:
    def __init__(
        self,
        store: SqliteIDEStore,
        inspector: RepositoryInspector | None = None,
    ) -> None:
        self.store = store
        self.inspector = inspector or RepositoryInspector()

    def open(self, path: Path) -> WorkspaceRecord:
        return self.store.open_workspace(self.inspector.inspect(path))

    def list(self) -> tuple[WorkspaceRecord, ...]:
        return self.store.list_workspaces()

    def get(self, workspace_id: UUID) -> WorkspaceRecord:
        return self.store.get_workspace(workspace_id)

    def entries(
        self, workspace_id: UUID, relative: str = "."
    ) -> tuple[WorkspaceEntry, ...]:
        workspace = self.get(workspace_id)
        return self.inspector.entries(workspace.root, relative)
```

Define `WorkspaceNotFoundError` in `store.py` and raise it for unknown UUIDs.

- [ ] **Step 5: Run focused workspace tests**

Run: `.venv/bin/pytest tests/unit/ide/test_store.py tests/unit/ide/test_workspaces.py -v`

Expected: all tests pass, including alias deduplication and store reconstruction.

- [ ] **Step 6: Commit the persistent workspace registry**

```bash
git add src/tcad_agent/ide/store.py src/tcad_agent/ide/workspaces.py \
  tests/unit/ide/test_store.py tests/unit/ide/test_workspaces.py
git commit -m "feat: persist local IDE workspaces"
```

### Task 3: Persistent Conversations, Messages, and Activity Events

**Files:**
- Modify: `src/tcad_agent/ide/models.py`
- Modify: `src/tcad_agent/ide/store.py`
- Create: `src/tcad_agent/ide/conversations.py`
- Create: `src/tcad_agent/ide/events.py`
- Create: `tests/unit/ide/test_conversations.py`
- Create: `tests/unit/ide/test_events.py`

**Interfaces:**
- Consumes: persisted workspace UUIDs from Task 2
- Produces: `ConversationRecord`, `ConversationMessage`, `IDEEvent`, and `ConversationState`
- Produces: `ConversationService.create()`, `.list()`, `.get()`, `.add_user_message()`, and `.messages()`
- Produces: `EventFeed.append()` and `.list_after()`
- Produces: `format_sse(event: IDEEvent) -> str`

- [ ] **Step 1: Write failing restart and event-ordering tests**

```python
from pathlib import Path

from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed, format_sse
from tcad_agent.ide.store import SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager


def test_conversation_messages_and_events_survive_restart(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    database = tmp_path / "ide.sqlite3"
    first_store = SqliteIDEStore(database)
    workspace = WorkspaceManager(first_store).open(root)
    first_service = ConversationService(first_store, EventFeed(first_store))
    conversation = first_service.create(workspace.id, "PN junction")
    message = first_service.add_user_message(conversation.id, "Inspect the repository")

    second_store = SqliteIDEStore(database)
    second_service = ConversationService(second_store, EventFeed(second_store))

    assert second_service.get(conversation.id).title == "PN junction"
    assert second_service.messages(conversation.id) == (message,)
    events = EventFeed(second_store).list_after(conversation.id, after_id=0)
    assert [event.kind for event in events] == [
        "conversation_created",
        "message_created",
    ]


def test_event_cursor_is_strictly_after_and_sse_has_an_id(tmp_path: Path) -> None:
    store = SqliteIDEStore(tmp_path / "ide.sqlite3")
    root = tmp_path / "repo"
    root.mkdir()
    workspace = WorkspaceManager(store).open(root)
    conversation = ConversationService(store, EventFeed(store)).create(
        workspace.id, "Reference"
    )
    feed = EventFeed(store)
    first = feed.append(conversation.id, "status_changed", {"status": "idle"})
    second = feed.append(conversation.id, "status_changed", {"status": "running"})

    assert feed.list_after(conversation.id, after_id=first.id) == (second,)
    assert format_sse(second).startswith(
        f"id: {second.id}\nevent: status_changed\ndata: "
    )
```

- [ ] **Step 2: Run tests and confirm conversation types are missing**

Run: `.venv/bin/pytest tests/unit/ide/test_conversations.py tests/unit/ide/test_events.py -v`

Expected: collection fails because the conversation and event modules do not exist.

- [ ] **Step 3: Add conversation and event contracts**

Add these types to `src/tcad_agent/ide/models.py`:

```python
from enum import StrEnum
from pydantic import JsonValue


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
```

- [ ] **Step 4: Add conversation, message, and event tables**

Extend `SqliteIDEStore.__init__` with foreign-keyed tables. The event identifier must be an
autoincrementing integer so it can serve as an SSE cursor.

```sql
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
```

Add store methods named `create_conversation`, `get_conversation`, `list_conversations`,
`append_message`, `list_messages`, `append_event`, and `list_events_after`. Each method must
return the typed model defined above and use deterministic `created_at, id` ordering.

- [ ] **Step 5: Implement conversation and event services**

`ConversationService.create(workspace_id, title)` validates that the workspace exists, normalizes
the title to stripped text of 1 to 120 characters, persists the conversation, and appends a
`conversation_created` event. `add_user_message` accepts stripped content of 1 to 100,000
characters, persists it, updates the conversation timestamp and revision, and appends a
`message_created` event whose payload contains the message UUID and role but not duplicated full
message text.

`EventFeed` delegates persistence to the store and exposes:

```python
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


def format_sse(event: IDEEvent) -> str:
    data = json.dumps(event.model_dump(mode="json"), sort_keys=True)
    return f"id: {event.id}\nevent: {event.kind}\ndata: {data}\n\n"
```

- [ ] **Step 6: Run conversation and event tests**

Run: `.venv/bin/pytest tests/unit/ide/test_conversations.py tests/unit/ide/test_events.py -v`

Expected: all tests pass, including process-style store reconstruction.

- [ ] **Step 7: Commit persistent conversations and activity**

```bash
git add src/tcad_agent/ide tests/unit/ide
git commit -m "feat: persist IDE conversations and events"
```

### Task 4: Workspace and Conversation HTTP API

**Files:**
- Modify: `src/tcad_agent/web/schemas.py`
- Create: `src/tcad_agent/web/ide_routes.py`
- Modify: `src/tcad_agent/web/app.py`
- Create: `tests/unit/web/test_ide_api.py`

**Interfaces:**
- Consumes: `WorkspaceManager`, `ConversationService`, and `EventFeed` from Tasks 2 and 3
- Produces: `build_ide_router(manager, conversations, events) -> APIRouter`
- Produces: `build_default_ide_services() -> IDEServices`
- Produces: workspace, conversation, message, tree, and SSE HTTP endpoints

- [ ] **Step 1: Write failing API tests**

```python
from pathlib import Path

from fastapi.testclient import TestClient

from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed
from tcad_agent.ide.store import SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager
from tcad_agent.web.app import create_app
from tcad_agent.web.ide_routes import IDEServices


def ide_client(tmp_path: Path) -> TestClient:
    store = SqliteIDEStore(tmp_path / "ide.sqlite3")
    events = EventFeed(store)
    services = IDEServices(
        workspaces=WorkspaceManager(store),
        conversations=ConversationService(store, events),
        events=events,
    )
    return TestClient(create_app(ide=services))


def test_workspace_conversation_and_tree_api(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("# Research\n")
    web = ide_client(tmp_path)

    opened = web.post("/api/workspaces", json={"path": str(root)})
    assert opened.status_code == 201
    workspace = opened.json()
    assert workspace["root"] == str(root.resolve())
    assert workspace["git"]["available"] is False

    entries = web.get(f"/api/workspaces/{workspace['id']}/entries")
    assert entries.json() == [
        {"path": "README.md", "name": "README.md", "kind": "file", "size": 11}
    ]

    created = web.post(
        f"/api/workspaces/{workspace['id']}/conversations",
        json={"title": "Inspect this repository"},
    )
    assert created.status_code == 201
    conversation = created.json()
    sent = web.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "Find the simulation entrypoint"},
    )
    assert sent.status_code == 201
    assert sent.json()["role"] == "user"


def test_sse_reconnect_honors_last_event_id_without_duplicates(tmp_path: Path) -> None:
    web = ide_client(tmp_path)
    root = tmp_path / "repo"
    root.mkdir()
    workspace = web.post("/api/workspaces", json={"path": str(root)}).json()
    conversation = web.post(
        f"/api/workspaces/{workspace['id']}/conversations",
        json={"title": "Reference"},
    ).json()
    web.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "Inspect files"},
    )
    all_events = web.get(
        f"/api/conversations/{conversation['id']}/events?follow=false"
    )
    first_id = int(all_events.text.splitlines()[0].removeprefix("id: "))

    resumed = web.get(
        f"/api/conversations/{conversation['id']}/events?follow=false",
        headers={"Last-Event-ID": str(first_id)},
    )

    assert f"id: {first_id}\n" not in resumed.text
    assert "event: message_created" in resumed.text
```

- [ ] **Step 2: Run focused API tests and confirm router imports fail**

Run: `.venv/bin/pytest tests/unit/web/test_ide_api.py -v`

Expected: collection fails because `tcad_agent.web.ide_routes` does not exist.

- [ ] **Step 3: Add strict HTTP schemas**

Add to `src/tcad_agent/web/schemas.py`:

```python
class OpenWorkspaceRequest(WebRequest):
    path: str = Field(min_length=1, max_length=4096)


class CreateConversationRequest(WebRequest):
    title: str = Field(min_length=1, max_length=120)


class CreateMessageRequest(WebRequest):
    content: str = Field(min_length=1, max_length=100_000)
```

- [ ] **Step 4: Implement the IDE router and exception mapping**

Create `IDEServices` as a frozen dataclass and `build_ide_router` in
`src/tcad_agent/web/ide_routes.py`. Expose:

```text
POST /api/workspaces
GET  /api/workspaces
GET  /api/workspaces/{workspace_id}
GET  /api/workspaces/{workspace_id}/entries?path=.
POST /api/workspaces/{workspace_id}/conversations
GET  /api/workspaces/{workspace_id}/conversations
GET  /api/conversations/{conversation_id}
GET  /api/conversations/{conversation_id}/messages
POST /api/conversations/{conversation_id}/messages
GET  /api/conversations/{conversation_id}/events?after=0&follow=true
```

The SSE route determines its cursor in this order: valid `Last-Event-ID` header, `after` query
parameter, then zero. With `follow=false`, return all currently available events and close. With
`follow=true`, poll `EventFeed.list_after` every 250 milliseconds, emit `: keepalive\n\n` after
15 seconds without activity, and stop when `request.is_disconnected()` is true.

Map invalid or missing paths to a structured 400 response, unknown workspace or conversation
UUIDs to 404, and stale conflicts to 409. Do not echo filesystem contents or exception tracebacks.

- [ ] **Step 5: Wire default IDE services into `create_app`**

Add an optional keyword argument `ide: IDEServices | None = None`. The default constructor uses
`TCAD_WORKSPACE` or `.tcad-agent` and stores the IDE database at
`<runtime-root>/ide.sqlite3`. Include the IDE router without changing existing request routes.

- [ ] **Step 6: Run new and existing API tests**

Run: `.venv/bin/pytest tests/unit/web/test_ide_api.py tests/unit/web/test_api.py -v`

Expected: all tests pass and the existing guided workflow remains available.

- [ ] **Step 7: Commit the local IDE API**

```bash
git add src/tcad_agent/web src/tcad_agent/ide tests/unit/web
git commit -m "feat: expose workspace conversation API"
```

### Task 5: Browser IDE Shell and Guided Workflow Routing

**Files:**
- Create: `src/tcad_agent/web/templates/ide.html`
- Create: `src/tcad_agent/web/static/ide.js`
- Create: `src/tcad_agent/web/static/ide.css`
- Modify: `src/tcad_agent/web/app.py`
- Modify: `src/tcad_agent/web/templates/index.html`
- Modify: `tests/unit/web/test_api.py`
- Create: `tests/e2e/test_ide_shell.py`

**Interfaces:**
- Consumes: HTTP endpoints from Task 4
- Produces: `/`, `/workspaces/{workspace_id}`, and
  `/workspaces/{workspace_id}/conversations/{conversation_id}` IDE shell routes
- Preserves: `/simulate` and `/requests/{request_id}/{stage}` guided TCAD routes

- [ ] **Step 1: Write failing shell and route tests**

Add parser assertions that `/` contains these stable elements:

```python
def test_root_serves_workspace_ide_shell(tmp_path: Path) -> None:
    page = client(tmp_path).get("/")
    parser = ButtonTextParser()
    parser.feed(page.text)

    assert parser.elements["workspace-browser"] == "aside"
    assert parser.elements["repository-tree"] == "div"
    assert parser.elements["workspace-main"] == "main"
    assert parser.elements["workspace-tabs"] == "nav"
    assert parser.elements["agent-panel"] == "aside"
    assert parser.elements["conversation-messages"] == "div"
    assert parser.elements["agent-activity"] == "div"
    assert parser.elements["open-workspace"] == "button"
    assert parser.elements["create-conversation"] == "button"


def test_guided_simulation_remains_available(tmp_path: Path) -> None:
    page = client(tmp_path).get("/simulate")
    assert page.status_code == 200
    assert 'id="workflow-progress"' in page.text
    assert 'id="results-workspace"' in page.text
```

Add an end-to-end browser-independent test that opens a workspace, creates a conversation, posts a
message, reloads the conversation route, and confirms the API still returns the persisted message
and event sequence.

- [ ] **Step 2: Run shell tests and verify the expected element failures**

Run: `.venv/bin/pytest tests/unit/web/test_api.py tests/e2e/test_ide_shell.py -v`

Expected: the root-shell assertions fail because `/` still serves the guided workflow.

- [ ] **Step 3: Create the semantic IDE template**

`ide.html` must include:

```html
<div class="ide-shell">
  <header class="ide-header">
    <a class="brand" href="/">Quiloo</a>
    <div id="workspace-status" aria-live="polite">No workspace open</div>
    <a href="/simulate">Guided simulation</a>
  </header>
  <aside id="workspace-browser" aria-label="Repository">
    <form id="workspace-form">
      <label for="workspace-path">Repository path</label>
      <input id="workspace-path" name="path" autocomplete="off">
      <button id="open-workspace" type="submit">Open workspace</button>
    </form>
    <div id="repository-tree" role="tree"></div>
  </aside>
  <main id="workspace-main">
    <nav id="workspace-tabs" aria-label="Workspace views"></nav>
    <section id="workspace-welcome"></section>
  </main>
  <aside id="agent-panel" aria-label="Agent conversation">
    <button id="create-conversation" type="button" disabled>New conversation</button>
    <div id="conversation-messages" aria-live="polite"></div>
    <div id="agent-activity" aria-live="polite"></div>
    <form id="message-form">
      <textarea id="message-input" disabled></textarea>
      <button id="send-message" type="submit" disabled>Send</button>
    </form>
  </aside>
</div>
```

Include an accessible modal for conversation title entry, an error notice, and a visible label
that this first slice persists prompts but does not yet execute the OpenHands loop.

- [ ] **Step 4: Implement route-aware browser behavior**

`ide.js` must:

1. Parse workspace and conversation UUIDs from the URL.
2. Open a typed repository path through `POST /api/workspaces`.
3. Navigate with `history.pushState` to `/workspaces/{id}`.
4. Render directory entries without using `innerHTML` for untrusted names.
5. Create and list conversations.
6. Load persisted messages.
7. Connect `EventSource` to the active conversation and append concrete activity events.
8. Reconnect after navigation without leaving the old `EventSource` open.
9. Post a user message and render the server response.
10. Restore the workspace and conversation after a full page reload.

All API failures must display the sanitized server message in the error notice. The current
repository path is displayed as text, not inserted as HTML.

- [ ] **Step 5: Add a professional three-panel Linux desktop layout**

`ide.css` must use the existing NovAtom visual variables where practical, provide a resizable-feel
three-column grid without JavaScript resizing in this slice, keep the chat input visible, support
keyboard focus states, and collapse the repository and activity panels below 900 pixels. Do not
copy the existing sequential page stack into the IDE.

- [ ] **Step 6: Move the guided workflow entry route without breaking deep links**

Change `src/tcad_agent/web/app.py` so:

- `/` renders `ide.html`.
- `/workspaces/{workspace_id}` renders `ide.html`.
- `/workspaces/{workspace_id}/conversations/{conversation_id}` renders `ide.html`.
- `/simulate` renders the existing `index.html`.
- Existing `/requests/{request_id}/{stage}` routes continue rendering `index.html`.

Add a small `Open IDE` link to the guided template header.

- [ ] **Step 7: Run shell and existing web tests**

Run: `.venv/bin/pytest tests/unit/web/test_api.py tests/unit/web/test_ide_api.py tests/e2e/test_ide_shell.py tests/e2e/test_web_workflow.py -v`

Expected: all tests pass, and both IDE and guided simulation routes are covered.

- [ ] **Step 8: Commit the browser IDE foundation**

```bash
git add src/tcad_agent/web tests/unit/web tests/e2e/test_ide_shell.py
git commit -m "feat: add persistent browser IDE shell"
```

### Task 6: Linux Launcher, Documentation, and End-to-End Verification

**Files:**
- Modify: `src/tcad_agent/web/launcher.py`
- Modify: `src/tcad_agent/cli.py`
- Modify: `tests/unit/web/test_web_runtime.py`
- Modify: `tests/e2e/test_cli_workflow.py`
- Modify: `README.md`
- Modify: `docs/architecture.md`

**Interfaces:**
- Consumes: the IDE routes and services from Tasks 1 through 5
- Produces: `tcad-agent serve --host 127.0.0.1 --port 8765`
- Produces: `run_server(host: str, port: int, open_browser: bool) -> None`
- Preserves: `tcad-agent-web` compatibility entrypoint

- [ ] **Step 1: Write failing Linux launcher tests**

Add a Typer CLI test:

```python
from typer.testing import CliRunner

from tcad_agent.cli import app


def test_serve_command_exposes_linux_local_options() -> None:
    result = CliRunner().invoke(app, ["serve", "--help"])

    assert result.exit_code == 0
    assert "--host" in result.stdout
    assert "--port" in result.stdout
    assert "--no-browser" in result.stdout
    assert "127.0.0.1" in result.stdout
```

Add launcher unit tests that monkeypatch `uvicorn.run` and `webbrowser.open`, call
`run_server("127.0.0.1", free_port, open_browser=False)`, and assert that no browser call occurs
and Uvicorn receives the supplied host and port.

- [ ] **Step 2: Run launcher tests and verify the missing command failure**

Run: `.venv/bin/pytest tests/unit/web/test_web_runtime.py tests/e2e/test_cli_workflow.py -v`

Expected: the new serve-command test fails because `serve` is not registered.

- [ ] **Step 3: Refactor the launcher into a reusable Linux entrypoint**

Refactor `src/tcad_agent/web/launcher.py` so `main()` delegates to:

```python
def run_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    open_browser: bool = True,
) -> None:
    if host != DEFAULT_HOST:
        raise ValueError("the pilot server must bind to 127.0.0.1")
    fingerprint = runtime_fingerprint()
    selected_port, reused = _select_port(port, fingerprint)
    url = f"http://{host}:{selected_port}"
    if reused:
        if open_browser:
            webbrowser.open(url)
        return
    if open_browser:
        threading.Thread(
            target=_open_when_ready,
            args=(url, fingerprint),
            daemon=True,
        ).start()
    uvicorn.run(
        create_app(runtime_id=fingerprint),
        host=host,
        port=selected_port,
        log_level="info",
    )
```

Update `_port_available` and `_select_port` to accept the host explicitly rather than relying on a
hidden module constant.

- [ ] **Step 4: Register `tcad-agent serve`**

Add a lazy-importing Typer command to `src/tcad_agent/cli.py`:

```python
@app.command("serve")
def serve_command(
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8765,
    no_browser: Annotated[bool, typer.Option("--no-browser")] = False,
) -> None:
    """Start the Linux-local Quiloo IDE and TCAD workflow."""
    from tcad_agent.web.launcher import run_server

    try:
        run_server(host, port, open_browser=not no_browser)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
```

- [ ] **Step 5: Update operator and architecture documentation**

Update `README.md` with:

- Linux prerequisites
- `.venv/bin/tcad-agent serve`
- `--no-browser` for headless launch
- Opening a repository and resuming a conversation
- The guided simulation link and `/simulate` route
- The exact current boundary: repository inspection and persisted prompts work in this slice;
  editing, terminal tools, approvals, and autonomous OpenHands execution are the next slices
- Local runtime database location and backup behavior

Update `docs/architecture.md` with the workspace, conversation, SSE, and route boundaries. Keep the
existing TCAD contracts unchanged.

- [ ] **Step 6: Run the complete automated suite**

Run: `.venv/bin/pytest -q`

Expected: all non-opt-in tests pass. The only skips are the documented live Bedrock and licensed
Sentaurus tests.

- [ ] **Step 7: Run full static and repository checks**

Run:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src/tcad_agent
git diff --check
```

Expected: all commands exit zero.

- [ ] **Step 8: Perform a Linux-style manual smoke test**

Run:

```bash
.venv/bin/tcad-agent serve --no-browser
```

Verify from a browser on the same machine:

1. `/` opens the IDE shell.
2. An existing Git repository and a plain directory can each be opened.
3. Directory entries render and external symlink targets cannot be opened.
4. A conversation can be created and a prompt can be persisted.
5. Reloading the conversation URL restores messages and activity.
6. `/simulate` opens the existing guided workflow.
7. A known DEVSIM example still runs and displays interactive results.

- [ ] **Step 9: Commit the Linux foundation documentation and launcher**

```bash
git add src/tcad_agent/cli.py src/tcad_agent/web/launcher.py \
  tests/unit/web/test_web_runtime.py tests/e2e/test_cli_workflow.py \
  README.md docs/architecture.md
git commit -m "feat: ship Linux-local workspace IDE foundation"
```

- [ ] **Step 10: Record the next vertical-slice boundary**

After this plan passes review, the next implementation plan must start from the persisted
`WorkspaceRecord`, `ConversationRecord`, `ConversationMessage`, and `IDEEvent` interfaces. It will
add atomic file reads and writes, repository search, bounded terminal execution, visible diffs,
and recoverable checkpoints. It must not replace or duplicate the contracts delivered here.
