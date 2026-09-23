from pathlib import Path

import pytest

from tcad_agent.control.models import RequestState, ResearchRequest
from tcad_agent.control.store import (
    ConcurrentTransitionError,
    IllegalTransitionError,
    SqliteRequestStore,
)


@pytest.fixture
def store(tmp_path: Path) -> SqliteRequestStore:
    return SqliteRequestStore(tmp_path / "requests.sqlite3")


def test_store_persists_requests_across_restart(
    store: SqliteRequestStore, tmp_path: Path
) -> None:
    record = store.create(ResearchRequest(prompt="simulate a junction"))
    reopened = SqliteRequestStore(tmp_path / "requests.sqlite3")
    assert reopened.get(record.id) == record


def test_transition_rejects_stale_revision(store: SqliteRequestStore) -> None:
    record = store.create(ResearchRequest(prompt="simulate a junction"))
    store.transition(
        record.id,
        record.revision,
        RequestState.NEEDS_CLARIFICATION,
        {"questions": ["geometry"]},
    )
    with pytest.raises(ConcurrentTransitionError):
        store.transition(
            record.id,
            record.revision,
            RequestState.SPEC_DRAFTED,
            {},
        )


def test_transition_rejects_skipped_lifecycle_state(store: SqliteRequestStore) -> None:
    record = store.create(ResearchRequest(prompt="simulate a junction"))
    with pytest.raises(IllegalTransitionError, match=r"requested.*running"):
        store.transition(
            record.id,
            record.revision,
            RequestState.RUNNING,
            {},
        )


def test_valid_transition_increments_revision_and_merges_data(
    store: SqliteRequestStore,
) -> None:
    record = store.create(ResearchRequest(prompt="simulate a junction"))
    updated = store.transition(
        record.id,
        record.revision,
        RequestState.NEEDS_CLARIFICATION,
        {"questions": ["geometry"]},
    )
    assert updated.state is RequestState.NEEDS_CLARIFICATION
    assert updated.revision == 1
    assert updated.data == {"questions": ["geometry"]}
