import json
from datetime import UTC, datetime

import pytest

from tcad_agent.events.ledger import EventLedger, EventLedgerIntegrityError
from tcad_agent.events.models import RunEventKind


def test_ledger_appends_sequence_and_hash_chain(tmp_path) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    first = ledger.append(
        RunEventKind.REQUESTED,
        {"request_id": "request-1"},
        occurred_at=datetime(2026, 9, 23, tzinfo=UTC),
    )
    second = ledger.append(
        RunEventKind.COMPILED,
        {"backend": "devsim"},
        occurred_at=datetime(2026, 9, 23, 0, 0, 1, tzinfo=UTC),
    )
    assert first.sequence == 1
    assert first.previous_hash is None
    assert second.sequence == 2
    assert second.previous_hash == first.event_hash
    assert ledger.verify() == (first, second)


def test_ledger_detects_mutated_payload(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    ledger = EventLedger(path)
    ledger.append(RunEventKind.REQUESTED, {"request_id": "request-1"})
    row = json.loads(path.read_text())
    row["payload"]["request_id"] = "tampered"
    path.write_text(json.dumps(row) + "\n")

    with pytest.raises(EventLedgerIntegrityError, match="hash"):
        ledger.verify()
