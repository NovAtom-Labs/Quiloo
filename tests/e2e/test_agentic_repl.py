from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from openhands.sdk.llm import Message, MessageToolCall, TextContent
from openhands.sdk.testing import TestLLM

from scripts.create_repl_test_repo import create_repository
from tcad_agent.agent.runtime import OpenHandsRuntimeFactory
from tcad_agent.agent.supervisor import AgentSupervisor
from tcad_agent.ide.conversations import ConversationService
from tcad_agent.ide.events import EventFeed
from tcad_agent.ide.models import RunState
from tcad_agent.ide.store import SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager
from tcad_agent.web.app import create_app
from tcad_agent.web.ide_routes import IDEServices

PROJECT_ROOT = Path(__file__).parents[2]
GRADER = PROJECT_ROOT / "evaluations/repl/grade_workspace.py"
ACCEPTANCE_PROMPT = (
    "Inspect this repository and RESEARCH_TASK.md. Diagnose and fix the scientific "
    "validation failures without changing researcher-owned inputs, run the repository "
    "checks, delegate a read-only scientific review, and report exact evidence."
)


def _tool_call(
    identifier: str, name: str, arguments: dict[str, object]
) -> Message:
    return Message(
        role="assistant",
        content=[TextContent(text="")],
        tool_calls=[
            MessageToolCall(
                id=identifier,
                name=name,
                arguments=json.dumps(
                    {
                        **arguments,
                        "security_risk": "LOW",
                        "summary": f"acceptance {name} operation",
                    }
                ),
                origin="completion",
            )
        ],
    )


def _scripted_responses(repository: Path) -> list[Message | Exception]:
    physics = repository / "src/junction_lab/physics.py"
    validation = repository / "src/junction_lab/validation.py"
    report = repository / "src/junction_lab/report.py"
    return [
        _tool_call(
            "view-task",
            "file_editor",
            {"command": "view", "path": str(repository / "RESEARCH_TASK.md")},
        ),
        _tool_call(
            "fix-field",
            "file_editor",
            {
                "command": "str_replace",
                "path": str(physics),
                "old_str": "return (2.0 * potential_v / width_m) / 100.0",
                "new_str": "return 2.0 * potential_v / width_m",
            },
        ),
        _tool_call(
            "fix-tolerance",
            "file_editor",
            {
                "command": "str_replace",
                "path": str(validation),
                "old_str": "<= tolerance_fraction * 0.01",
                "new_str": "<= tolerance_fraction",
            },
        ),
        _tool_call(
            "fix-provenance",
            "file_editor",
            {
                "command": "str_replace",
                "path": str(report),
                "old_str": (
                    "    del input_sha256\n"
                    "    return \"\\n\".join("
                ),
                "new_str": "    return \"\\n\".join(",
            },
        ),
        _tool_call(
            "add-provenance",
            "file_editor",
            {
                "command": "str_replace",
                "path": str(report),
                "old_str": (
                    '            f"Model: {summary[\'model_version\']}",\n'
                    '            "",'
                ),
                "new_str": (
                    '            f"Model: {summary[\'model_version\']}",\n'
                    '            f"Input SHA-256: {input_sha256}",\n'
                    '            "",'
                ),
            },
        ),
        _tool_call(
            "run-checks",
            "terminal",
            {
                "command": (
                    f"{shlex.quote(sys.executable)} scripts/check.py"
                )
            },
        ),
        _tool_call(
            "delegate-review",
            "task",
            {
                "description": "Review the scientific repair",
                "prompt": (
                    "Read the repaired physics, validation, and report code. "
                    "Confirm units, tolerance semantics, provenance, and test evidence."
                ),
                "subagent_type": "tcad-reviewer",
            },
        ),
        _tool_call(
            "review-file",
            "file_editor",
            {"command": "view", "path": str(physics)},
        ),
        Message(
            role="assistant",
            content=[
                TextContent(
                    text=(
                        "Scientific review passed: electric field remains in V/m, "
                        "tolerance is fractional, and provenance is retained."
                    )
                )
            ],
        ),
        Message(
            role="assistant",
            content=[
                TextContent(
                    text=(
                        "Repaired three independent scientific defects. "
                        "Evidence: scripts/check.py passed 5 tests; the TCAD review "
                        "confirmed V/m units, fractional tolerance, and input SHA-256 "
                        "provenance. Researcher-owned experiment, data, and tests were "
                        "not changed."
                    )
                )
            ],
        ),
    ]


def _services(tmp_path: Path) -> IDEServices:
    store = SqliteIDEStore(tmp_path / "runtime/ide.sqlite3")
    events = EventFeed(store)
    return IDEServices(
        workspaces=WorkspaceManager(store),
        conversations=ConversationService(store, events),
        events=events,
    )


def _start_through_http(
    web: TestClient, repository: Path
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    workspace = web.post("/api/workspaces", json={"path": str(repository)}).json()
    conversation = web.post(
        f"/api/workspaces/{workspace['id']}/conversations",
        json={"title": "Repair junction validation"},
    ).json()
    message = web.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": ACCEPTANCE_PROMPT},
    ).json()
    response = web.post(
        f"/api/conversations/{conversation['id']}/runs",
        json={"message_id": message["id"]},
    )
    assert response.status_code == 202, response.text
    return workspace, conversation, response.json()


def test_repository_agent_repairs_validates_and_delegates_end_to_end(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "pn-junction-research")
    llm = TestLLM.from_messages(_scripted_responses(repository))
    services = _services(tmp_path)
    supervisor = AgentSupervisor(
        services,
        OpenHandsRuntimeFactory(services.runtime_root, llm=llm),
    )
    web = TestClient(
        create_app(ide=services, agent_supervisor=supervisor),
        raise_server_exceptions=True,
    )

    _workspace, conversation, started = _start_through_http(web, repository)
    run_id = UUID(str(started["id"]))
    conversation_id = UUID(str(conversation["id"]))
    supervisor.join(run_id, timeout=30)

    completed = services.store.get_run(run_id)
    messages = web.get(
        f"/api/conversations/{conversation['id']}/messages"
    ).json()
    activity = services.events.list_after(conversation_id, 0)
    grade = subprocess.run(
        [sys.executable, str(GRADER), "--workspace", str(repository)],
        check=False,
        capture_output=True,
        text=True,
    )
    changed = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    assert completed.state is RunState.COMPLETED
    assert messages[-1]["role"] == "assistant"
    assert "passed 5 tests" in messages[-1]["content"]
    assert json.loads(grade.stdout) == {
        "checks": {
            "generalizes_beyond_reference": True,
            "protected_inputs": True,
            "scientific_artifacts": True,
            "visible_tests": True,
        },
        "passed": True,
        "score": 100,
    }
    assert changed == [
        "src/junction_lab/physics.py",
        "src/junction_lab/report.py",
        "src/junction_lab/validation.py",
    ]
    completed_tools = [
        event for event in activity if event.kind == "tool_call_completed"
    ]
    assert any("Ran 5 tests" in str(event.payload) for event in completed_tools), [
        event.payload for event in completed_tools
    ]
    assert any(event.payload.get("task_id") for event in completed_tools)
    assert llm.remaining_responses == 0


@pytest.mark.live_bedrock
def test_live_bedrock_repository_agent_is_opt_in(
    pytestconfig: pytest.Config,
    tmp_path: Path,
) -> None:
    if not pytestconfig.getoption("--run-live-bedrock"):
        pytest.skip("pass --run-live-bedrock to call the configured Bedrock model")
    if not os.getenv("AWS_BEARER_TOKEN_BEDROCK"):
        pytest.skip("AWS_BEARER_TOKEN_BEDROCK is not configured")
    repository = create_repository(tmp_path / "pn-junction-research")
    services = _services(tmp_path)
    supervisor = AgentSupervisor(
        services,
        OpenHandsRuntimeFactory(services.runtime_root),
    )
    web = TestClient(create_app(ide=services, agent_supervisor=supervisor))

    _workspace, _conversation, started = _start_through_http(web, repository)
    run_id = UUID(str(started["id"]))
    supervisor.join(run_id, timeout=300)

    assert services.store.get_run(run_id).state is RunState.COMPLETED
    grade = subprocess.run(
        [sys.executable, str(GRADER), "--workspace", str(repository)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert grade.returncode == 0, grade.stdout
