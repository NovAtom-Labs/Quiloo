from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from tcad_agent.desktop.session_storage import DesktopSessionStorage
from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed
from tcad_agent.ide.models import RunState
from tcad_agent.ide.store import IDEStoreError, SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager
from tcad_agent.web.app import create_app
from tcad_agent.web.ide_routes import IDEServices


def _application(
    runtime_root: Path,
) -> tuple[SqliteIDEStore, IDEServices, TestClient]:
    store = SqliteIDEStore(runtime_root / "ide.sqlite3")
    events = EventFeed(store)
    services = IDEServices(
        workspaces=WorkspaceManager(store),
        conversations=ConversationService(store, events),
        events=events,
    )
    return store, services, TestClient(create_app(ide=services))


def _open_session(web: TestClient, repository: Path) -> tuple[dict, str]:
    workspace = web.post(
        "/api/workspaces", json={"path": str(repository)}
    ).json()
    session_url = f"/api/workspaces/{workspace['id']}/session"
    session = web.post(session_url)
    assert session.status_code == 200
    return session.json(), session_url


def test_restart_discards_messages_runs_approvals_events_and_openhands_state(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "application-data"
    repository = tmp_path / "repository"
    repository.mkdir()
    first_storage = DesktopSessionStorage.prepare(data_dir)
    first_store, first_services, first_web = _application(first_storage.runtime_root)
    session, session_url = _open_session(first_web, repository)
    message = first_web.post(
        f"{session_url}/messages", json={"content": "Run validation"}
    ).json()
    run = first_store.create_run(UUID(session["id"]), UUID(session["id"]))
    approval = first_store.create_approval(
        run.id,
        "action-1",
        "terminal",
        "HIGH",
        "Install a package",
        {"command": "python -m pip install package"},
    )
    first_services.events.append(
        UUID(session["id"]), "technical_activity", {"run_id": str(run.id)}
    )
    openhands_state = (
        first_storage.runtime_root / "openhands" / UUID(session["id"]).hex
    )
    openhands_state.mkdir(parents=True)
    (openhands_state / "events.jsonl").write_text("temporary", encoding="utf-8")

    first_storage.cleanup()
    second_storage = DesktopSessionStorage.prepare(data_dir)
    second_store, _second_services, second_web = _application(
        second_storage.runtime_root
    )
    second_session, second_url = _open_session(second_web, repository)

    assert second_session["id"] != session["id"]
    assert second_web.get(f"{second_url}/messages").json() == []
    assert second_web.get(f"{second_url}/runs/active").json() is None
    assert not first_storage.runtime_root.exists()
    assert not openhands_state.exists()
    for getter, identifier in (
        (second_store.get_message, UUID(message["id"])),
        (second_store.get_run, run.id),
        (second_store.get_approval, approval.id),
    ):
        with pytest.raises(IDEStoreError):
            getter(identifier)
    second_storage.cleanup()


def test_restart_preserves_repository_artifacts_settings_and_credentials(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "application-data"
    repository = tmp_path / "repository"
    artifact = repository / "results" / "equilibrium.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"validated":true}', encoding="utf-8")
    (data_dir / "settings.json").parent.mkdir(parents=True)
    (data_dir / "settings.json").write_text("settings", encoding="utf-8")
    (data_dir / "secrets.bin").write_bytes(b"protected")
    storage = DesktopSessionStorage.prepare(data_dir)
    _store, _services, web = _application(storage.runtime_root)
    _open_session(web, repository)

    storage.cleanup()
    restarted = DesktopSessionStorage.prepare(data_dir)

    assert artifact.read_text(encoding="utf-8") == '{"validated":true}'
    assert (data_dir / "settings.json").read_text(encoding="utf-8") == "settings"
    assert (data_dir / "secrets.bin").read_bytes() == b"protected"
    restarted.cleanup()


def test_crash_recovery_removes_stale_session_before_new_workspace_opens(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "application-data"
    stale = data_dir / "sessions" / "abandoned-process"
    stale.mkdir(parents=True)
    (stale / "ide.sqlite3").write_text("stale", encoding="utf-8")

    storage = DesktopSessionStorage.prepare(data_dir)
    _store, _services, web = _application(storage.runtime_root)
    repository = tmp_path / "repository"
    repository.mkdir()
    session, _session_url = _open_session(web, repository)

    assert not stale.exists()
    assert session["workspace_id"]
    assert storage.runtime_root.is_dir()
    storage.cleanup()


def test_switching_repository_after_completed_run_clears_chat_and_activity(
    tmp_path: Path,
) -> None:
    storage = DesktopSessionStorage.prepare(tmp_path / "application-data")
    store, services, web = _application(storage.runtime_root)
    first_repository = tmp_path / "first"
    second_repository = tmp_path / "second"
    first_repository.mkdir()
    second_repository.mkdir()
    first_session, first_url = _open_session(web, first_repository)
    web.post(f"{first_url}/messages", json={"content": "Inspect first"})
    run = store.create_run(UUID(first_session["id"]), UUID(first_session["id"]))
    store.transition_run(run.id, run.revision, RunState.COMPLETED)
    services.events.append(
        UUID(first_session["id"]), "technical_activity", {"run_id": str(run.id)}
    )

    second_session, second_url = _open_session(web, second_repository)

    assert second_session["id"] != first_session["id"]
    assert web.get(f"{second_url}/messages").json() == []
    assert web.get(f"{second_url}/runs/active").json() is None
    assert web.get(f"{second_url}/events?follow=false").text.count("event:") == 1
    assert web.get(f"{first_url}/events?follow=false").status_code == 404
    storage.cleanup()


def test_switching_repository_during_live_run_is_rejected_without_file_loss(
    tmp_path: Path,
) -> None:
    storage = DesktopSessionStorage.prepare(tmp_path / "application-data")
    store, services, web = _application(storage.runtime_root)
    first_repository = tmp_path / "first"
    second_repository = tmp_path / "second"
    first_repository.mkdir()
    second_repository.mkdir()
    artifact = first_repository / "results" / "field.csv"
    artifact.parent.mkdir()
    artifact.write_text("x,field\n0,1\n", encoding="utf-8")
    first_session, _first_url = _open_session(web, first_repository)
    run = store.create_run(UUID(first_session["id"]), UUID(first_session["id"]))
    second_workspace = services.workspaces.open(second_repository)

    response = web.post(f"/api/workspaces/{second_workspace.id}/session")

    assert response.status_code == 409
    assert response.json()["code"] == "workspace_session_busy"
    assert services.sessions.current().id == UUID(first_session["id"])
    assert store.get_run(run.id).state is RunState.QUEUED
    assert artifact.read_text(encoding="utf-8") == "x,field\n0,1\n"
    storage.cleanup()
