import platform
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from openhands.sdk.conversation import ConversationExecutionStatus
from openhands.sdk.event import ActionEvent, MessageEvent
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.llm.message import MessageToolCall
from openhands.sdk.security import SecurityRisk
from openhands.tools.terminal.definition import TerminalAction

from tcad_agent.agent.supervisor import AgentSupervisor
from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed
from tcad_agent.ide.store import SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager
from tcad_agent.web import ide_routes
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


class ApprovalConversation:
    def __init__(self, conversation_id: UUID, callback) -> None:
        self.id = conversation_id
        self.callback = callback
        self.state = SimpleNamespace(
            execution_status=ConversationExecutionStatus.IDLE
        )
        self.run_count = 0

    def send_message(self, message: str, sender: str | None = None) -> None:
        del message, sender

    def run(self) -> None:
        self.run_count += 1
        if self.run_count == 1:
            self.callback(
                ActionEvent(
                    thought=[],
                    action=TerminalAction(command="git push"),
                    tool_name="terminal",
                    tool_call_id="push-1",
                    tool_call=MessageToolCall(
                        id="push-1",
                        name="terminal",
                        arguments='{"command":"git push"}',
                        origin="completion",
                    ),
                    llm_response_id="response-1",
                    security_risk=SecurityRisk.LOW,
                )
            )
            self.state.execution_status = (
                ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
            )
            return
        self.callback(
            MessageEvent(
                source="agent",
                llm_message=Message(
                    role="assistant",
                    content=[TextContent(text="Push approved and task completed")],
                ),
            )
        )
        self.state.execution_status = ConversationExecutionStatus.FINISHED

    def pause(self) -> None:
        self.state.execution_status = ConversationExecutionStatus.PAUSED

    def interrupt(self) -> None:
        self.state.execution_status = ConversationExecutionStatus.PAUSED

    def reject_pending_actions(self, reason: str = "User rejected") -> None:
        del reason


class ApprovalRuntimeFactory:
    def create(self, workspace: Path, conversation_id: UUID, callback):
        assert workspace.is_dir()
        return ApprovalConversation(conversation_id, callback)


def test_agent_run_and_approval_api_lifecycle(tmp_path: Path) -> None:
    store = SqliteIDEStore(tmp_path / "ide.sqlite3")
    events = EventFeed(store)
    services = IDEServices(
        workspaces=WorkspaceManager(store),
        conversations=ConversationService(store, events),
        events=events,
    )
    supervisor = AgentSupervisor(services, ApprovalRuntimeFactory())
    web = TestClient(create_app(ide=services, agent_supervisor=supervisor))
    root = tmp_path / "repo"
    root.mkdir()
    workspace = web.post("/api/workspaces", json={"path": str(root)}).json()
    conversation = web.post(
        f"/api/workspaces/{workspace['id']}/conversations",
        json={"title": "Approval workflow"},
    ).json()
    message = web.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "Inspect, edit, test, and push only if I approve"},
    ).json()

    started = web.post(
        f"/api/conversations/{conversation['id']}/runs",
        json={"message_id": message["id"]},
    )
    assert started.status_code == 202
    run = started.json()
    supervisor.join(UUID(run["id"]), timeout=2)

    active = web.get(
        f"/api/conversations/{conversation['id']}/runs/active"
    )
    approvals = web.get(
        f"/api/conversations/{conversation['id']}/approvals"
    )
    duplicate = web.post(
        f"/api/conversations/{conversation['id']}/runs",
        json={"message_id": message["id"]},
    )

    assert active.status_code == 200
    assert active.json()["state"] == "waiting_for_approval"
    assert approvals.status_code == 200
    approval = approvals.json()[0]
    assert approval["payload"] == {"command": "git push"}
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "agent_run_conflict"

    approved = web.post(
        f"/api/approvals/{approval['id']}/approve",
        json={"expected_revision": approval["revision"]},
    )
    assert approved.status_code == 200
    supervisor.join(UUID(run["id"]), timeout=2)

    messages = web.get(
        f"/api/conversations/{conversation['id']}/messages"
    ).json()
    stale = web.post(
        f"/api/approvals/{approval['id']}/approve",
        json={"expected_revision": approval["revision"]},
    )
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[-1]["content"] == "Push approved and task completed"
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_revision"


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


def test_local_directory_picker_returns_selected_directory(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "selected-repository"
    root.mkdir()
    monkeypatch.setattr(
        ide_routes,
        "select_directory",
        lambda: root,
        raising=False,
    )

    response = ide_client(tmp_path).post("/api/system/directories/select")

    assert response.status_code == 200
    assert response.json() == {"path": str(root)}


def test_local_directory_picker_reports_cancellation(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        ide_routes,
        "select_directory",
        lambda: None,
        raising=False,
    )

    response = ide_client(tmp_path).post("/api/system/directories/select")

    assert response.status_code == 200
    assert response.json() == {"path": None}


def test_linux_directory_picker_uses_available_native_dialog(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "chosen"
    root.mkdir()
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(
        shutil,
        "which",
        lambda command: "/usr/bin/zenity" if command == "zenity" else None,
    )

    def run_dialog(
        command: list[str], **_options: object
    ) -> subprocess.CompletedProcess[str]:
        assert command == [
            "/usr/bin/zenity",
            "--file-selection",
            "--directory",
            "--title=Open repository folder",
        ]
        return subprocess.CompletedProcess(command, 0, f"{root}\n", "")

    monkeypatch.setattr(subprocess, "run", run_dialog)

    assert ide_routes.select_directory() == root.resolve()


def test_headless_linux_directory_picker_has_safe_error(monkeypatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    with pytest.raises(RuntimeError, match="graphical desktop"):
        ide_routes.select_directory()


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


def test_finite_sse_response_returns_complete_event_history(tmp_path: Path) -> None:
    store = SqliteIDEStore(tmp_path / "ide.sqlite3")
    events = EventFeed(store)
    services = IDEServices(
        workspaces=WorkspaceManager(store),
        conversations=ConversationService(store, events),
        events=events,
    )
    web = TestClient(create_app(ide=services))
    root = tmp_path / "repo"
    root.mkdir()
    workspace = web.post("/api/workspaces", json={"path": str(root)}).json()
    conversation = web.post(
        f"/api/workspaces/{workspace['id']}/conversations",
        json={"title": "Long activity history"},
    ).json()
    for sequence in range(205):
        events.append(
            conversation_id=conversation["id"],
            kind="status_changed",
            payload={"sequence": sequence},
        )

    response = web.get(
        f"/api/conversations/{conversation['id']}/events?follow=false"
    )

    assert response.status_code == 200
    assert response.text.count("event: status_changed") == 205


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


def test_missing_child_workspace_path_is_a_sanitized_client_error(
    tmp_path: Path,
) -> None:
    web = ide_client(tmp_path)
    root = tmp_path / "repo"
    root.mkdir()
    workspace = web.post("/api/workspaces", json={"path": str(root)}).json()

    response = web.get(
        f"/api/workspaces/{workspace['id']}/entries?path=deleted-directory"
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "invalid_workspace_path",
        "message": "The workspace path is unavailable or invalid.",
    }
    assert "deleted-directory" not in response.text
