from pathlib import Path

from fastapi.testclient import TestClient

from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed
from tcad_agent.ide.store import SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager
from tcad_agent.web.app import create_app
from tcad_agent.web.ide_routes import IDEServices


def test_workspace_conversation_route_restores_persisted_activity(
    tmp_path: Path,
) -> None:
    store = SqliteIDEStore(tmp_path / "ide.sqlite3")
    events = EventFeed(store)
    app = create_app(
        ide=IDEServices(
            workspaces=WorkspaceManager(store),
            conversations=ConversationService(store, events),
            events=events,
        )
    )
    web = TestClient(app)
    root = tmp_path / "repo"
    root.mkdir()
    (root / "experiment.yaml").write_text("name: reference\n")

    workspace = web.post("/api/workspaces", json={"path": str(root)}).json()
    conversation = web.post(
        f"/api/workspaces/{workspace['id']}/conversations",
        json={"title": "Inspect experiment"},
    ).json()
    posted = web.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "Inspect the experiment definition"},
    )

    restored_page = web.get(
        f"/workspaces/{workspace['id']}/conversations/{conversation['id']}"
    )
    restored_messages = web.get(
        f"/api/conversations/{conversation['id']}/messages"
    ).json()
    restored_events = web.get(
        f"/api/conversations/{conversation['id']}/events?follow=false"
    ).text

    assert posted.status_code == 201
    assert restored_page.status_code == 200
    assert 'id="agent-panel"' in restored_page.text
    assert [message["content"] for message in restored_messages] == [
        "Inspect the experiment definition"
    ]
    assert "event: conversation_created" in restored_events
    assert "event: message_created" in restored_events
