from pathlib import Path

import pytest

from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed
from tcad_agent.ide.models import ApprovalDecision, RunState
from tcad_agent.ide.store import IDEStoreError, SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager


def test_workspace_survives_store_reconstruction(tmp_path: Path) -> None:
    root = tmp_path / "plain-directory"
    root.mkdir()
    database = tmp_path / "ide.sqlite3"
    created = WorkspaceManager(SqliteIDEStore(database)).open(root)

    reopened = WorkspaceManager(SqliteIDEStore(database)).get(created.id)

    assert reopened.root == root.resolve()
    assert reopened.git.available is False


def test_run_and_pending_approval_survive_store_reconstruction(
    tmp_path: Path,
) -> None:
    database = tmp_path / "ide.sqlite3"
    store = SqliteIDEStore(database)
    workspace = WorkspaceManager(store).open(tmp_path)
    conversation = ConversationService(store, EventFeed(store)).create(
        workspace.id, "Agent task"
    )
    run = store.create_run(conversation.id, conversation.id)
    approval = store.create_approval(
        run.id,
        "action-1",
        "terminal",
        "HIGH",
        "git commit",
        {"command": "git commit"},
    )

    restored = SqliteIDEStore(database)

    assert restored.get_run(run.id).state is RunState.WAITING_FOR_APPROVAL
    assert restored.list_pending_approvals(conversation.id) == (approval,)


def test_run_transitions_reject_a_stale_revision(tmp_path: Path) -> None:
    store = SqliteIDEStore(tmp_path / "ide.sqlite3")
    workspace = WorkspaceManager(store).open(tmp_path)
    conversation = ConversationService(store, EventFeed(store)).create(
        workspace.id, "Agent task"
    )
    run = store.create_run(conversation.id, conversation.id)
    running = store.transition_run(run.id, run.revision, RunState.RUNNING)

    with pytest.raises(IDEStoreError, match="stale run revision"):
        store.transition_run(run.id, run.revision, RunState.COMPLETED)

    assert store.get_run(run.id) == running


def test_approval_resolution_is_optimistic_and_persisted(tmp_path: Path) -> None:
    store = SqliteIDEStore(tmp_path / "ide.sqlite3")
    workspace = WorkspaceManager(store).open(tmp_path)
    conversation = ConversationService(store, EventFeed(store)).create(
        workspace.id, "Agent task"
    )
    run = store.create_run(conversation.id, conversation.id)
    approval = store.create_approval(
        run.id,
        "action-1",
        "terminal",
        "HIGH",
        "install package",
        {"command": "pip install package"},
    )

    resolved = store.resolve_approval(
        approval.id, approval.revision, ApprovalDecision.APPROVE
    )

    assert resolved.decision is ApprovalDecision.APPROVE
    assert resolved.resolved_at is not None
    assert store.list_pending_approvals(conversation.id) == ()
    with pytest.raises(IDEStoreError, match="stale approval revision"):
        store.resolve_approval(
            approval.id, approval.revision, ApprovalDecision.DENY
        )


def test_terminal_run_does_not_expose_stale_pending_approval(tmp_path: Path) -> None:
    store = SqliteIDEStore(tmp_path / "ide.sqlite3")
    workspace = WorkspaceManager(store).open(tmp_path)
    conversation = ConversationService(store, EventFeed(store)).create(
        workspace.id, "Agent task"
    )
    run = store.create_run(conversation.id, conversation.id)
    store.create_approval(
        run.id,
        "action-1",
        "terminal",
        "HIGH",
        "install package",
        {"command": "pip install package"},
    )
    waiting = store.get_run(run.id)
    store.transition_run(run.id, waiting.revision, RunState.CANCELLED)

    assert store.list_pending_approvals(conversation.id) == ()
