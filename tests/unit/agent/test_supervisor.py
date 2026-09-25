from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import UUID

import pytest
from openhands.sdk.conversation import ConversationExecutionStatus
from openhands.sdk.event import ActionEvent, MessageEvent, ObservationEvent
from openhands.sdk.event import Event as OpenHandsEvent
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.llm.message import MessageToolCall
from openhands.sdk.security import SecurityRisk
from openhands.sdk.tool import Observation
from openhands.tools.terminal.definition import TerminalAction

from tcad_agent.agent.supervisor import AgentRunConflictError, AgentSupervisor
from tcad_agent.ide.changes import WorkspaceChangeTracker
from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed
from tcad_agent.ide.models import ApprovalDecision, RunState
from tcad_agent.ide.store import SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager


class _TestObservation(Observation):
    pass


def tool_start() -> ActionEvent:
    return ActionEvent(
        thought=[],
        action=TerminalAction(command="pytest -q"),
        tool_name="terminal",
        tool_call_id="call-1",
        tool_call=MessageToolCall(
            id="call-1", name="terminal", arguments="{}", origin="completion"
        ),
        llm_response_id="response-1",
        security_risk=SecurityRisk.LOW,
    )


def tool_finish(action: ActionEvent) -> ObservationEvent:
    return ObservationEvent(
        tool_name="terminal",
        tool_call_id=action.tool_call_id,
        action_id=action.id,
        observation=_TestObservation.from_text("186 passed"),
    )


def assistant(content: str) -> MessageEvent:
    return MessageEvent(
        source="agent",
        llm_message=Message(role="assistant", content=[TextContent(text=content)]),
    )


@dataclass
class ScriptedState:
    execution_status: ConversationExecutionStatus = ConversationExecutionStatus.IDLE


class ScriptedConversation:
    def __init__(
        self,
        conversation_id: UUID,
        callback,
        events: list[OpenHandsEvent],
        final_status: ConversationExecutionStatus,
        gate: Event | None = None,
    ) -> None:
        self.id = conversation_id
        self.callback = callback
        self.events = events
        self.final_status = final_status
        self.gate = gate
        self.state = ScriptedState()
        self.messages: list[str] = []
        self.rejections: list[str] = []

    def send_message(self, message: str, sender: str | None = None) -> None:
        del sender
        self.messages.append(message)

    def run(self) -> None:
        self.state.execution_status = ConversationExecutionStatus.RUNNING
        if self.gate is not None:
            self.gate.wait(timeout=2)
        for item in self.events:
            self.callback(item)
        self.state.execution_status = self.final_status

    def pause(self) -> None:
        self.state.execution_status = ConversationExecutionStatus.PAUSED

    def interrupt(self) -> None:
        self.state.execution_status = ConversationExecutionStatus.PAUSED

    def reject_pending_actions(self, reason: str = "User rejected") -> None:
        self.rejections.append(reason)


class ScriptedRuntimeFactory:
    def __init__(
        self,
        events: list[OpenHandsEvent],
        *,
        status: ConversationExecutionStatus = ConversationExecutionStatus.FINISHED,
        gate: Event | None = None,
    ) -> None:
        self.events = events
        self.status = status
        self.gate = gate
        self.created: list[ScriptedConversation] = []

    def create(self, workspace: Path, conversation_id: UUID, callback):
        assert workspace.is_dir()
        conversation = ScriptedConversation(
            conversation_id,
            callback,
            self.events,
            self.status,
            self.gate,
        )
        self.created.append(conversation)
        return conversation


@pytest.fixture
def services(tmp_path: Path):
    store = SqliteIDEStore(tmp_path / "ide.sqlite3")
    events = EventFeed(store)
    workspaces = WorkspaceManager(store)
    workspace = workspaces.open(tmp_path)
    conversations = ConversationService(store, events)
    conversation = conversations.create(workspace.id, "Agent task")
    return SimpleNamespace(
        store=store,
        events=events,
        workspaces=workspaces,
        conversations=conversations,
        changes=WorkspaceChangeTracker(),
        conversation=conversation,
        runtime_root=tmp_path / ".runtime",
    )


def test_start_captures_baseline_before_runtime_executes(services) -> None:
    observed = {"baseline_present": False}

    class BaselineObservingConversation(ScriptedConversation):
        def run(self) -> None:
            run = services.store.list_runs(services.conversation.id)[-1]
            observed["baseline_present"] = (
                services.store.get_run_baseline(run.id) is not None
            )
            super().run()

    class BaselineObservingFactory(ScriptedRuntimeFactory):
        def create(self, workspace: Path, conversation_id: UUID, callback):
            conversation = BaselineObservingConversation(
                conversation_id,
                callback,
                self.events,
                self.status,
                self.gate,
            )
            self.created.append(conversation)
            return conversation

    supervisor = AgentSupervisor(services, BaselineObservingFactory([]))

    run = supervisor.start(services.conversation.id, "repair and validate")
    supervisor.join(run.id, timeout=2)

    assert observed["baseline_present"] is True
    assert services.store.get_run_baseline(run.id).root == services.workspaces.get(
        services.conversation.workspace_id
    ).root


def test_supervisor_runs_in_background_and_persists_final_answer(services) -> None:
    action = tool_start()
    runtime = ScriptedRuntimeFactory(
        events=[action, tool_finish(action), assistant("Completed")]
    )
    supervisor = AgentSupervisor(services, runtime)

    run = supervisor.start(
        services.conversation.id, "Inspect and test the repository"
    )
    supervisor.join(run.id, timeout=2)

    assert services.store.get_run(run.id).state is RunState.COMPLETED
    assert services.store.get_run_change_manifest(run.id) is not None
    assert services.store.list_messages(services.conversation.id)[-1].content == "Completed"
    kinds = [
        event.kind
        for event in services.events.iter_after(services.conversation.id, 0)
    ]
    for expected in (
        "run_started",
        "tool_call_started",
        "tool_call_completed",
        "run_completed",
    ):
        assert expected in kinds


def test_supervisor_rejects_a_second_active_writer(services) -> None:
    gate = Event()
    supervisor = AgentSupervisor(services, ScriptedRuntimeFactory([], gate=gate))
    first = supervisor.start(services.conversation.id, "Run tests")

    with pytest.raises(AgentRunConflictError):
        supervisor.start(services.conversation.id, "Edit files too")

    gate.set()
    supervisor.join(first.id, timeout=2)


def test_approval_resumes_and_denial_rejects_pending_action(services) -> None:
    runtime = ScriptedRuntimeFactory(
        [], status=ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
    )
    supervisor = AgentSupervisor(services, runtime)
    run = supervisor.start(services.conversation.id, "Push changes")
    supervisor.join(run.id, timeout=2)
    approval = services.store.create_approval(
        run.id,
        "action-1",
        "terminal",
        "HIGH",
        "terminal: git push",
        {"command": "git push"},
    )

    resumed = supervisor.deny(approval.id, approval.revision, "Keep changes local")
    supervisor.join(run.id, timeout=2)

    resolved = services.store.get_approval(approval.id)
    assert resolved.decision is ApprovalDecision.DENY
    assert runtime.created[0].rejections == ["Keep changes local"]
    assert resumed.id == run.id


def test_approve_category_grants_only_the_current_run(services) -> None:
    runtime = ScriptedRuntimeFactory(
        [], status=ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
    )
    supervisor = AgentSupervisor(services, runtime)
    run = supervisor.start(services.conversation.id, "Push changes")
    supervisor.join(run.id, timeout=2)
    approval = services.store.create_approval(
        run.id,
        "action-1",
        "terminal",
        "HIGH",
        "Agent Kronig wants to change Git history or send changes online.",
        {"command": "git push"},
        permission_category="git_mutation",
    )

    resumed = supervisor.approve_category(approval.id, approval.revision)
    supervisor.join(run.id, timeout=2)

    assert resumed.id == run.id
    assert services.store.list_run_permission_grants(run.id) == ("git_mutation",)


def test_stop_cancels_pending_approval(services) -> None:
    runtime = ScriptedRuntimeFactory(
        [], status=ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
    )
    supervisor = AgentSupervisor(services, runtime)
    run = supervisor.start(services.conversation.id, "Request a risky action")
    supervisor.join(run.id, timeout=2)
    approval = services.store.create_approval(
        run.id,
        "action-1",
        "terminal",
        "HIGH",
        "terminal: git push",
        {"command": "git push"},
    )

    cancelled = supervisor.stop(run.id)

    assert cancelled.state is RunState.CANCELLED
    assert services.store.get_approval(approval.id).decision is ApprovalDecision.DENY
    assert services.store.list_pending_approvals(services.conversation.id) == ()


def test_restart_recovery_pauses_interrupted_running_run(services) -> None:
    run = services.store.create_run(
        services.conversation.id, services.conversation.id
    )
    services.store.transition_run(run.id, run.revision, RunState.RUNNING)

    AgentSupervisor(services, ScriptedRuntimeFactory([]))

    assert services.store.get_run(run.id).state is RunState.PAUSED
