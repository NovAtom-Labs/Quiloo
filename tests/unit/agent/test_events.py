from pathlib import Path
from uuid import UUID

from openhands.sdk.agent.stream_context import StreamAborted, StreamDelta, StreamStarted
from openhands.sdk.event import ActionEvent, MessageEvent, ObservationEvent
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.llm.message import MessageToolCall
from openhands.sdk.security import SecurityRisk
from openhands.sdk.tool import Observation
from openhands.tools.terminal.definition import TerminalAction

from tcad_agent.agent.events import AgentEventBridge, structured_action_metadata
from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed
from tcad_agent.ide.store import SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager


class _TestObservation(Observation):
    pass


def _services(tmp_path: Path):
    store = SqliteIDEStore(tmp_path / "ide.sqlite3")
    events = EventFeed(store)
    workspace = WorkspaceManager(store).open(tmp_path)
    conversations = ConversationService(store, events)
    conversation = conversations.create(workspace.id, "Agent task")
    run = store.create_run(conversation.id, conversation.id)
    return store, events, conversations, conversation, run


def _terminal_action(command: str, *, risk: SecurityRisk) -> ActionEvent:
    return ActionEvent(
        thought=[TextContent(text="private chain of thought")],
        reasoning_content="private reasoning",
        action=TerminalAction(command=command),
        tool_name="terminal",
        tool_call_id="call-1",
        tool_call=MessageToolCall(
            id="call-1",
            name="terminal",
            arguments="{}",
            origin="completion",
        ),
        llm_response_id="response-1",
        security_risk=risk,
    )


def test_event_bridge_persists_normalized_tool_and_assistant_events(
    tmp_path: Path, monkeypatch
) -> None:
    store, events, conversations, conversation, run = _services(tmp_path)
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "secret-value")
    bridge = AgentEventBridge(conversation.id, run.id, store, events, conversations)
    action = _terminal_action("pytest -q --token secret-value", risk=SecurityRisk.LOW)
    observation = ObservationEvent(
        tool_name="terminal",
        tool_call_id="call-1",
        action_id=action.id,
        observation=_TestObservation.from_text("x" * 20_000 + " secret-value"),
    )
    answer = MessageEvent(
        source="agent",
        llm_message=Message(
            role="assistant", content=[TextContent(text="Completed safely")]
        ),
    )

    bridge(action)
    bridge(observation)
    bridge(answer)

    activity = events.list_after(conversation.id, 0)
    serialized = " ".join(str(event.payload) for event in activity)
    assert "secret-value" not in serialized
    assert "private chain of thought" not in serialized
    assert "private reasoning" not in serialized
    assert max(len(str(event.payload)) for event in activity) < 17_000
    assert [event.kind for event in activity][-3:] == [
        "tool_call_started",
        "tool_call_completed",
        "message_created",
    ]
    started = activity[-3].payload
    assert started["phase"] == "validate"
    assert started["evidence_kind"] == "validation"
    assert conversations.messages(conversation.id)[-1].content == "Completed safely"


def test_high_risk_action_creates_one_pending_approval(tmp_path: Path) -> None:
    store, events, conversations, conversation, run = _services(tmp_path)
    bridge = AgentEventBridge(conversation.id, run.id, store, events, conversations)
    action = _terminal_action("git push", risk=SecurityRisk.HIGH)

    bridge(action)

    approvals = store.list_pending_approvals(conversation.id)
    assert len(approvals) == 1
    assert approvals[0].action_id == action.id
    assert approvals[0].payload == {"command": "git push"}
    assert approvals[0].permission_category.value == "git_mutation"
    assert approvals[0].summary.startswith("Quiloo wants to change Git history")
    assert store.get_run(run.id).state.value == "waiting_for_approval"


def test_event_bridge_skips_approval_for_a_granted_run_category(
    tmp_path: Path,
) -> None:
    store, events, conversations, conversation, run = _services(tmp_path)
    bridge = AgentEventBridge(
        conversation.id,
        run.id,
        store,
        events,
        conversations,
        workspace=tmp_path,
        permission_grants={"git_mutation"},
    )

    bridge(_terminal_action("git push", risk=SecurityRisk.HIGH))

    assert store.list_pending_approvals(conversation.id) == ()
    grant_events = [
        event
        for event in events.list_after(conversation.id, 0)
        if event.kind == "permission_grant_used"
    ]
    assert len(grant_events) == 1
    assert grant_events[0].payload["permission_category"] == "git_mutation"


def test_on_stream_never_persists_private_model_reasoning(
    tmp_path: Path, monkeypatch
) -> None:
    store, events, conversations, conversation, run = _services(tmp_path)
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "secret-value")
    bridge = AgentEventBridge(conversation.id, run.id, store, events, conversations)

    bridge.on_stream(StreamStarted(item_id="item-1", attempt=1, anchor_seq=None))
    bridge.on_stream(
        StreamDelta(
            item_id="item-1",
            attempt=1,
            order=0,
            kind="reasoning",
            content="thinking about it, token secret-value",
        )
    )
    bridge.on_stream(
        StreamAborted(item_id="item-1", attempt=1, reason="cancelled")
    )

    activity = events.list_after(conversation.id, 0)
    serialized = " ".join(str(event.payload) for event in activity)
    assert "thinking about it" not in serialized
    assert "secret-value" not in serialized
    assert not {
        "thinking_started",
        "thinking_delta",
        "thinking_aborted",
    } & {event.kind for event in activity}


def test_bridge_accepts_uuid_identifiers(tmp_path: Path) -> None:
    store, events, conversations, conversation, run = _services(tmp_path)

    bridge = AgentEventBridge(
        UUID(str(conversation.id)), UUID(str(run.id)), store, events, conversations
    )

    assert bridge.conversation_id == conversation.id


def test_structured_phase_metadata_uses_typed_command_semantics() -> None:
    validation = structured_action_metadata(
        _terminal_action(
            'cd "/workspace" && python scripts/check.py 2>&1',
            risk=SecurityRisk.LOW,
        )
    )
    inspection = structured_action_metadata(
        _terminal_action("cat checks/input.txt", risk=SecurityRisk.LOW)
    )

    assert validation == {"phase": "validate", "evidence_kind": "validation"}
    assert inspection == {"phase": "inspect"}
