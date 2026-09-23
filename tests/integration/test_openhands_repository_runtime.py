from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from openhands.sdk.llm import Message, MessageToolCall, TextContent
from openhands.sdk.testing import TestLLM

from tcad_agent.agent.runtime import OpenHandsRuntimeFactory
from tcad_agent.agent.supervisor import AgentSupervisor
from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed
from tcad_agent.ide.models import RunState
from tcad_agent.ide.store import SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager


def tool_call(identifier: str, name: str, arguments: dict[str, object]) -> Message:
    payload = {
        **arguments,
        "security_risk": "LOW",
        "summary": f"test {name} operation",
    }
    return Message(
        role="assistant",
        content=[TextContent(text="")],
        tool_calls=[
            MessageToolCall(
                id=identifier,
                name=name,
                arguments=json.dumps(payload),
                origin="completion",
            )
        ],
    )


def test_openhands_edits_tests_and_delegates_inside_repository(tmp_path: Path) -> None:
    repository = tmp_path / "device-repository"
    repository.mkdir()
    (repository / "device.txt").write_text("mobility = 100\n")
    (repository / "test_device.py").write_text(
        "from pathlib import Path\n\n"
        "def test_mobility():\n"
        "    assert Path('device.txt').read_text() == 'mobility = 120\\n'\n"
    )
    subprocess.run(["git", "init", "-q", str(repository)], check=True)

    responses: list[Message | Exception] = [
        tool_call(
            "view-1",
            "file_editor",
            {"command": "view", "path": str(repository / "device.txt")},
        ),
        tool_call(
            "edit-1",
            "file_editor",
            {
                "command": "str_replace",
                "path": str(repository / "device.txt"),
                "old_str": "mobility = 100",
                "new_str": "mobility = 120",
            },
        ),
        tool_call(
            "test-1",
            "terminal",
            {"command": f"{shlex.quote(sys.executable)} -m pytest -q"},
        ),
        tool_call(
            "task-1",
            "task",
            {
                "description": "Review edited device",
                "prompt": "Read device.txt and report the mobility value.",
                "subagent_type": "code-explorer",
            },
        ),
        tool_call(
            "child-read-1",
            "terminal",
            {"command": "sed -n 1,20p device.txt"},
        ),
        Message(
            role="assistant",
            content=[TextContent(text="Reviewed device.txt: mobility is 120.")],
        ),
        Message(
            role="assistant",
            content=[TextContent(text="Updated mobility, tests pass, review complete.")],
        ),
    ]
    llm = TestLLM.from_messages(responses)

    database = tmp_path / "runtime" / "ide.sqlite3"
    store = SqliteIDEStore(database)
    events = EventFeed(store)
    workspaces = WorkspaceManager(store)
    workspace = workspaces.open(repository)
    conversations = ConversationService(store, events)
    conversation = conversations.create(workspace.id, "Update and review")
    services = SimpleNamespace(
        store=store,
        events=events,
        workspaces=workspaces,
        conversations=conversations,
        runtime_root=tmp_path / "runtime",
    )
    supervisor = AgentSupervisor(
        services,
        OpenHandsRuntimeFactory(tmp_path / "runtime", llm=llm),
    )

    run = supervisor.start(
        conversation.id,
        "Update the mobility to 120, run tests, then delegate a read-only review.",
    )
    supervisor.join(run.id, timeout=20)

    assert store.get_run(run.id).state is RunState.COMPLETED
    assert (repository / "device.txt").read_text() == "mobility = 120\n"
    messages = conversations.messages(conversation.id)
    assert messages[-1].content == "Updated mobility, tests pass, review complete."
    activity = events.list_after(conversation.id, 0)
    completed = [event for event in activity if event.kind == "tool_call_completed"]
    assert any("1 passed" in str(event.payload) for event in completed), [
        event.payload for event in completed
    ]
    assert any(event.payload.get("task_id") for event in completed)
    assert [event.kind for event in activity].count("tool_call_started") == 4
    assert llm.remaining_responses == 0
