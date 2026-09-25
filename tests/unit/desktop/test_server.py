import socket
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from tcad_agent.control.models import RequestState, ResearchRequest
from tcad_agent.control.service import ControlService
from tcad_agent.control.store import SqliteRequestStore
from tcad_agent.desktop.config import DesktopLaunchConfig
from tcad_agent.desktop.server import bind_desktop_socket, readiness_record
from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed
from tcad_agent.ide.models import RunState
from tcad_agent.ide.store import SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager
from tcad_agent.model_gateway.base import ScriptedModelGateway
from tcad_agent.web.app import create_app
from tcad_agent.web.ide_routes import IDEServices


def test_readiness_record_has_fixed_protocol_fields(tmp_path: Path) -> None:
    config = DesktopLaunchConfig(
        host="127.0.0.1",
        port=0,
        launch_token="x" * 43,
        data_dir=tmp_path,
    )

    assert readiness_record(
        config,
        url="http://127.0.0.1:49152",
        pid=312,
        fingerprint="a1b2c3d4",
    ) == {
        "protocol": 1,
        "url": "http://127.0.0.1:49152",
        "pid": 312,
        "runtime_fingerprint": "a1b2c3d4",
    }


def test_desktop_socket_uses_loopback_and_operating_system_port(tmp_path: Path) -> None:
    config = DesktopLaunchConfig(
        host="127.0.0.1",
        port=0,
        launch_token="x" * 43,
        data_dir=tmp_path,
    )

    listener = bind_desktop_socket(config)
    try:
        host, port = listener.getsockname()
        assert host == "127.0.0.1"
        assert isinstance(port, int) and port > 0
        with socket.create_connection((host, port), timeout=0.2):
            pass
    finally:
        listener.close()


def test_desktop_status_reports_active_run_state(tmp_path: Path) -> None:
    store = SqliteIDEStore(tmp_path / "ide.sqlite3")
    events = EventFeed(store)
    services = IDEServices(
        workspaces=WorkspaceManager(store),
        conversations=ConversationService(store, events),
        events=events,
    )
    client = TestClient(create_app(ide=services))
    root = tmp_path / "repo"
    root.mkdir()
    workspace = services.workspaces.open(root)
    conversation = services.conversations.create(workspace.id, "Desktop status")
    run = store.create_run(conversation.id, uuid4())

    assert client.get("/api/desktop/status").json() == {"active": True}

    store.transition_run(run.id, run.revision, RunState.COMPLETED)
    assert client.get("/api/desktop/status").json() == {"active": False}


def test_desktop_status_includes_active_simulation_request(tmp_path: Path) -> None:
    store = SqliteRequestStore(tmp_path / "requests.sqlite3")
    record = store.create(ResearchRequest(prompt="Run the reviewed experiment"))
    for state in (
        RequestState.SPEC_DRAFTED,
        RequestState.SPEC_VALIDATED,
        RequestState.USER_CONFIRMATION_REQUIRED,
        RequestState.COMPILED,
        RequestState.RUNNING,
    ):
        record = store.transition(record.id, record.revision, state, {})
    control = ControlService(
        store=store,
        gateway=ScriptedModelGateway(()),
        workspace=tmp_path / "workspace",
    )

    response = TestClient(create_app(control=control)).get("/api/desktop/status")

    assert response.json() == {"active": True}
