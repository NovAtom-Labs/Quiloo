from pathlib import Path
from uuid import uuid4

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


def test_sse_reconnect_honors_last_event_id_without_duplicates(
    tmp_path: Path,
) -> None:
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


def test_invalid_workspace_paths_and_unknown_records_are_sanitized(
    tmp_path: Path,
) -> None:
    web = ide_client(tmp_path)
    missing = tmp_path / "company-secret-directory-name"

    invalid = web.post("/api/workspaces", json={"path": str(missing)})
    unknown = web.get(f"/api/workspaces/{uuid4()}")

    assert invalid.status_code == 400
    assert invalid.json() == {
        "code": "invalid_workspace_path",
        "message": "The workspace path is unavailable or invalid.",
    }
    assert str(missing) not in invalid.text
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "workspace_not_found"
