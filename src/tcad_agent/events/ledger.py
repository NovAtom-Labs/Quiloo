"""Append-only JSONL event ledger with SHA-256 hash chaining."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import JsonValue, ValidationError

from tcad_agent.events.models import RunEvent, RunEventKind


class EventLedgerIntegrityError(ValueError):
    pass


class EventLedger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(
        self,
        kind: RunEventKind,
        payload: dict[str, JsonValue],
        *,
        occurred_at: datetime | None = None,
    ) -> RunEvent:
        events = self.verify() if self.path.exists() else ()
        timestamp = occurred_at or datetime.now(UTC)
        if timestamp.tzinfo is None:
            raise ValueError("event timestamps must include a timezone")
        sequence = len(events) + 1
        previous_hash = events[-1].event_hash if events else None
        material = self._material(sequence, timestamp, kind, payload, previous_hash)
        event = RunEvent(
            sequence=sequence,
            occurred_at=timestamp,
            kind=kind,
            payload=payload,
            previous_hash=previous_hash,
            event_hash=self._hash(material),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(event.model_dump_json() + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return event

    def verify(self) -> tuple[RunEvent, ...]:
        if not self.path.exists():
            return ()
        events: list[RunEvent] = []
        previous_hash: str | None = None
        for expected_sequence, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            try:
                event = RunEvent.model_validate_json(line)
            except ValidationError as exc:
                raise EventLedgerIntegrityError("event ledger contains an invalid row") from exc
            if event.sequence != expected_sequence:
                raise EventLedgerIntegrityError("event ledger sequence is not contiguous")
            if event.previous_hash != previous_hash:
                raise EventLedgerIntegrityError("event ledger previous hash does not match")
            material = self._material(
                event.sequence,
                event.occurred_at,
                event.kind,
                event.payload,
                event.previous_hash,
            )
            if event.event_hash != self._hash(material):
                raise EventLedgerIntegrityError("event ledger hash does not match its content")
            events.append(event)
            previous_hash = event.event_hash
        return tuple(events)

    @staticmethod
    def _material(
        sequence: int,
        occurred_at: datetime,
        kind: RunEventKind,
        payload: dict[str, JsonValue],
        previous_hash: str | None,
    ) -> bytes:
        data = {
            "kind": kind.value,
            "occurred_at": occurred_at.isoformat(),
            "payload": payload,
            "previous_hash": previous_hash,
            "sequence": sequence,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()

    @staticmethod
    def _hash(material: bytes) -> str:
        return hashlib.sha256(material).hexdigest()
