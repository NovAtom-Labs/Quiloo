# Agentic Repository Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the local Quiloo IDE to a persistent OpenHands runtime that can inspect and edit a selected repository, execute commands, invoke typed TCAD tools, delegate bounded tasks to subagents, request approval for risky actions, stream activity, and resume after browser or service restarts.

**Architecture:** Keep the existing SQLite workspace, conversation, and event contracts as the product record. Add a runtime supervisor that owns OpenHands conversations and maps SDK events into those contracts. OpenHands supplies the file editor, terminal, task tracker, and task delegation tools; Quiloo supplies the simulator-neutral TCAD tool, repository policy, state transitions, API, and browser presentation.

**Tech Stack:** Python 3.13, OpenHands SDK and Tools 1.49.4, Amazon Bedrock through LiteLLM, FastAPI, SQLite WAL, Server-Sent Events, vanilla JavaScript, pytest, Ruff, mypy

**Spec:** `docs/superpowers/specs/2026-09-24-linux-local-agent-ide-design.md`

## Global Constraints

- Bind the application to `127.0.0.1` by default and refuse native host actions from non-loopback clients.
- Target Linux and use POSIX behavior. Development fallbacks may support macOS and Windows but must not become required runtime dependencies.
- Treat `ExperimentSpec` as the only simulator-neutral scientific execution contract.
- Keep simulator syntax inside adapter packages and preserve the guided DEVSIM and Sentaurus workflow.
- Use OpenHands SDK and Tools `1.49.4` through their public interfaces.
- Configure the pilot with one Bedrock model through `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION_NAME`, `LLM_MODEL`, and `TCAD_REASONING_EFFORT`.
- Never persist or stream credentials, model reasoning, or unrestricted environment values.
- Routine repository reads, edits, searches, tests, and validation may run without interruption. External paths, network changes, package installation, destructive commands, Git commits, and Git pushes require an approval boundary.
- Subagents inherit the parent workspace and policy. They cannot widen permissions.
- Do not overwrite or revert pre-existing user changes.
- Add each behavior with a failing test first and run the full suite before each implementation commit.

## Review Focus

- An agent or subagent action containing an external absolute path, traversal, destructive command, package installation, Git mutation, or remote mutation must stop for approval before execution. Task 2 tests these classifications.
- Two simultaneous prompts for the same conversation or workspace must not start concurrent writers. Task 3 tests writer locking and duplicate-run rejection.
- Browser refresh and service reconstruction must preserve messages, run state, OpenHands persistence identifiers, and ordered events. Tasks 1 and 3 test reconstruction.
- SDK events containing tool arguments or observations must be size-bounded and secret-redacted before SQLite persistence or SSE delivery. Task 3 tests redaction and clipping.
- A delegated subagent must use the same workspace and confirmation policy and its result must be attributed to its task. Task 4 tests registered delegation and event attribution.

---

### Task 1: Persistent run and approval contracts

**Files:**
- Modify: `src/tcad_agent/ide/models.py`
- Modify: `src/tcad_agent/ide/store.py`
- Modify: `src/tcad_agent/ide/conversations.py`
- Modify: `src/tcad_agent/ide/events.py`
- Test: `tests/unit/ide/test_store.py`
- Test: `tests/unit/ide/test_conversations.py`

**Interfaces:**
- Produces: `AgentRunRecord`, `ApprovalRequestRecord`, `ApprovalDecision`, and `RunState`
- Produces: `SqliteIDEStore.create_run(conversation_id, sdk_conversation_id) -> AgentRunRecord`
- Produces: `SqliteIDEStore.transition_run(run_id, expected_revision, state) -> AgentRunRecord`
- Produces: `SqliteIDEStore.create_approval(run_id, action_id, tool_name, risk, summary, payload) -> ApprovalRequestRecord`
- Produces: `SqliteIDEStore.resolve_approval(approval_id, expected_revision, decision) -> ApprovalRequestRecord`
- Produces: `ConversationService.add_assistant_message(conversation_id, content) -> ConversationMessage`

- [ ] **Step 1: Write failing persistence tests**

```python
def test_run_and_pending_approval_survive_store_reconstruction(tmp_path: Path) -> None:
    store = SqliteIDEStore(tmp_path / "ide.sqlite3")
    workspace = WorkspaceManager(store).open(tmp_path)
    events = EventFeed(store)
    conversation = ConversationService(store, events).create(workspace.id, "Agent task")
    run = store.create_run(conversation.id, conversation.id)
    approval = store.create_approval(
        run.id, "action-1", "terminal", "HIGH", "git commit", {"command": "git commit"}
    )

    restored = SqliteIDEStore(tmp_path / "ide.sqlite3")

    assert restored.get_run(run.id).state == RunState.WAITING_FOR_APPROVAL
    assert restored.list_pending_approvals(conversation.id) == (approval,)
```

- [ ] **Step 2: Run the tests and confirm they fail because the run schema is absent**

Run: `.venv/bin/pytest tests/unit/ide/test_store.py tests/unit/ide/test_conversations.py -q`

- [ ] **Step 3: Add strict run and approval models**

Use UUID identifiers, UTC timestamps, non-negative revisions, explicit enums, and JSON-safe payloads. Keep approval payloads bounded to the normalized tool call that the user is deciding.

- [ ] **Step 4: Add idempotent SQLite migrations and optimistic transitions**

Create `agent_runs` and `approval_requests` tables with foreign keys. Every state mutation uses `WHERE id = ? AND revision = ?`; a stale update raises `IDEStoreError` and never silently wins.

- [ ] **Step 5: Add assistant-message persistence and lifecycle events**

`add_assistant_message` must append the message and a `message_created` event. Run and approval mutations must append their event only after the database mutation commits.

- [ ] **Step 6: Run focused tests**

Run: `.venv/bin/pytest tests/unit/ide -q`

- [ ] **Step 7: Commit**

```bash
git add src/tcad_agent/ide tests/unit/ide
git commit -m "feat: persist agent runs and approvals"
```

### Task 2: Workspace-aware action policy

**Files:**
- Create: `src/tcad_agent/agent/policy.py`
- Test: `tests/unit/agent/test_policy.py`

**Interfaces:**
- Produces: `WorkspaceSecurityAnalyzer(SecurityAnalyzerBase)`
- Produces: `classify_action(workspace: Path, event: ActionEvent) -> SecurityRisk`
- Produces: `action_summary(event: ActionEvent) -> str`

- [ ] **Step 1: Write failing policy tests**

```python
@pytest.mark.parametrize("command", ["pytest -q", "git diff", "rg TODO src"])
def test_repository_commands_are_low_risk(workspace: Path, command: str) -> None:
    assert classify_action(workspace, terminal_event(command)) is SecurityRisk.LOW

@pytest.mark.parametrize(
    "command",
    ["pip install x", "git commit -am x", "git push", "rm -rf build", "cat /etc/passwd"],
)
def test_external_or_mutating_commands_require_confirmation(
    workspace: Path, command: str
) -> None:
    assert classify_action(workspace, terminal_event(command)) is SecurityRisk.HIGH

def test_file_action_outside_workspace_requires_confirmation(workspace: Path) -> None:
    assert classify_action(workspace, file_event("/tmp/external.txt")) is SecurityRisk.HIGH
```

- [ ] **Step 2: Run the tests and confirm the policy module is absent**

Run: `.venv/bin/pytest tests/unit/agent/test_policy.py -q`

- [ ] **Step 3: Implement conservative typed classification**

Inspect `FileEditorAction.path`, `TerminalAction.command`, and task actions. Canonicalize paths at decision time. Mark external paths, traversal, network utilities, installers, destructive operations, credential paths, Git staging or mutation, and unknown action types `HIGH`. Mark repository-local file reads and edits plus allowlisted inspection, build, test, lint, and simulator commands `LOW`. Mark delegated tasks `MEDIUM`; their child tool calls are still classified separately.

- [ ] **Step 4: Add safe action summaries**

Summaries include the tool, canonical target or clipped command, and risk reason. They exclude file contents, environment values, credentials, and model reasoning.

- [ ] **Step 5: Run focused tests**

Run: `.venv/bin/pytest tests/unit/agent/test_policy.py -q`

- [ ] **Step 6: Commit**

```bash
git add src/tcad_agent/agent/policy.py tests/unit/agent/test_policy.py
git commit -m "feat: classify agent actions by workspace risk"
```

### Task 3: OpenHands runtime supervisor and event bridge

**Files:**
- Create: `src/tcad_agent/agent/events.py`
- Create: `src/tcad_agent/agent/supervisor.py`
- Modify: `src/tcad_agent/agent/runtime.py`
- Modify: `src/tcad_agent/web/ide_routes.py`
- Test: `tests/unit/agent/test_events.py`
- Test: `tests/unit/agent/test_supervisor.py`

**Interfaces:**
- Produces: `OpenHandsRuntimeFactory.create(workspace, conversation_id, callback) -> LocalConversation`
- Produces: `AgentEventBridge(conversation_id, run_id, store, events)` callable
- Produces: `AgentSupervisor.start(conversation_id, prompt) -> AgentRunRecord`
- Produces: `AgentSupervisor.approve(approval_id, expected_revision) -> AgentRunRecord`
- Produces: `AgentSupervisor.deny(approval_id, expected_revision, reason) -> AgentRunRecord`
- Produces: `AgentSupervisor.pause(run_id)`, `resume(run_id)`, and `stop(run_id)`

- [ ] **Step 1: Write failing bridge and supervisor tests**

```python
def test_supervisor_runs_in_background_and_persists_final_answer(services) -> None:
    runtime = ScriptedRuntime(events=[tool_start(), tool_finish(), assistant("Completed")])
    supervisor = AgentSupervisor(services, runtime)

    run = supervisor.start(services.conversation.id, "Inspect and test the repository")
    supervisor.join(run.id, timeout=2)

    assert services.store.get_run(run.id).state == RunState.COMPLETED
    assert services.store.list_messages(services.conversation.id)[-1].content == "Completed"
    assert [event.kind for event in services.events.iter_after(services.conversation.id, 0)] >= [
        "run_started", "tool_call_started", "tool_call_completed", "run_completed"
    ]
```

- [ ] **Step 2: Run the tests and confirm the supervisor module is absent**

Run: `.venv/bin/pytest tests/unit/agent/test_events.py tests/unit/agent/test_supervisor.py -q`

- [ ] **Step 3: Build the production OpenHands agent**

Construct `LLM` from the existing Bedrock environment contract. Register OpenHands `TerminalTool`, `FileEditorTool`, `TaskTrackerTool`, `TaskToolSet`, the built-in subagent definitions, project `.agents/agents` definitions, and `TcadDomainTool`. Use the default condenser, a bounded iteration count, a persistence directory beneath the Quiloo runtime root, `visualizer=None`, and `ConfirmRisky` with `WorkspaceSecurityAnalyzer`.

- [ ] **Step 4: Map SDK events into stable product events**

Map message, action, observation, pause, interrupt, error, and execution-status events. Store only normalized fields. Clip individual text fields at 16,000 characters, redact configured secret values and common credential patterns, and never store internal reasoning blocks.

- [ ] **Step 5: Implement one-writer background execution**

Use one daemon thread per active conversation and a workspace lock keyed by canonical root. Persist `RUNNING` before starting. A second write-capable run returns a typed conflict. On SDK confirmation wait, persist an approval and `WAITING_FOR_APPROVAL`. On approval call `conversation.run()` again. On denial call `reject_pending_actions()` and continue so the model can choose another safe path.

- [ ] **Step 6: Implement pause, resume, stop, and process-restart recovery**

Pause calls the SDK pause method and persists `PAUSED`. Resume reconstructs the SDK conversation from its UUID and persistence directory before running. Stop interrupts active work and persists `CANCELLED`. Startup converts runs interrupted in `RUNNING` to `PAUSED`; pending approvals stay pending.

- [ ] **Step 7: Run focused tests**

Run: `.venv/bin/pytest tests/unit/agent tests/unit/ide -q`

- [ ] **Step 8: Commit**

```bash
git add src/tcad_agent/agent src/tcad_agent/web/ide_routes.py tests/unit/agent
git commit -m "feat: connect persistent OpenHands runtime"
```

### Task 4: Tool calling and delegated subagents integration

**Files:**
- Create: `tests/integration/test_openhands_repository_runtime.py`
- Modify: `src/tcad_agent/agent/runtime.py`
- Create: `.agents/agents/tcad-researcher.md`
- Create: `.agents/agents/tcad-reviewer.md`

**Interfaces:**
- Consumes: OpenHands `TestLLM`, `TaskToolSet`, built-in subagent registration, `TcadDomainTool`
- Produces: an executable OpenHands conversation with file, terminal, TCAD, and task-delegation tools

- [ ] **Step 1: Write a deterministic OpenHands integration test**

Use `TestLLM` tool-call messages to make the primary agent view a fixture file, edit it, run its tests, delegate a read-only review, and finish. Assert the repository content, command observation, task observation, final assistant message, and ordered Quiloo events. Use a temporary Git repository and no network.

- [ ] **Step 2: Run the integration test and confirm missing runtime wiring**

Run: `.venv/bin/pytest tests/integration/test_openhands_repository_runtime.py -q`

- [ ] **Step 3: Add TCAD specialist definitions**

`tcad-researcher` receives terminal inspection plus `tcad_domain` and is instructed to return cited, structured scientific findings. `tcad-reviewer` receives read-only inspection and `tcad_domain` validation operations and is instructed to check units, capability support, requested outputs, and evidence without modifying files.

- [ ] **Step 4: Register built-in and project subagents per conversation**

Registration must be idempotent in one process. Disable the web-research subagent by default because network access requires separate product policy and credentials. Limit delegated children and inherit parent confirmation policy and budget.

- [ ] **Step 5: Run the integration test**

Run: `.venv/bin/pytest tests/integration/test_openhands_repository_runtime.py -q`

- [ ] **Step 6: Commit**

```bash
git add .agents src/tcad_agent/agent/runtime.py tests/integration/test_openhands_repository_runtime.py
git commit -m "feat: enable tool use and delegated agents"
```

### Task 5: Runtime HTTP API

**Files:**
- Modify: `src/tcad_agent/web/schemas.py`
- Modify: `src/tcad_agent/web/ide_routes.py`
- Modify: `src/tcad_agent/web/app.py`
- Test: `tests/unit/web/test_ide_api.py`
- Test: `tests/e2e/test_ide_shell.py`

**Interfaces:**
- Produces: `POST /api/conversations/{id}/runs`
- Produces: `GET /api/conversations/{id}/runs/active`
- Produces: `POST /api/runs/{id}/pause`, `/resume`, and `/stop`
- Produces: `GET /api/conversations/{id}/approvals`
- Produces: `POST /api/approvals/{id}/approve` and `/deny`

- [ ] **Step 1: Write failing API lifecycle tests**

Create a workspace and conversation, send a prompt, start a run, observe `202 Accepted`, receive run and tool events, resolve a pending approval with the expected revision, and retrieve the persisted assistant response. Test stale revision rejection and duplicate active-run conflict.

- [ ] **Step 2: Run the API tests and confirm the routes are missing**

Run: `.venv/bin/pytest tests/unit/web/test_ide_api.py tests/e2e/test_ide_shell.py -q`

- [ ] **Step 3: Add strict request schemas and runtime routes**

Routes validate UUIDs and expected revisions, return stable error codes, and never expose credentials, raw provider errors, or Python tracebacks. Starting a run is non-blocking.

- [ ] **Step 4: Preserve the existing message route**

Posting a user message persists it. The frontend then starts a run explicitly with that message ID, preventing accidental duplicate execution when a client retries message creation.

- [ ] **Step 5: Run focused tests**

Run: `.venv/bin/pytest tests/unit/web tests/e2e/test_ide_shell.py -q`

- [ ] **Step 6: Commit**

```bash
git add src/tcad_agent/web tests/unit/web tests/e2e/test_ide_shell.py
git commit -m "feat: expose agent run and approval API"
```

### Task 6: Live IDE agent workflow

**Files:**
- Modify: `src/tcad_agent/web/templates/ide.html`
- Modify: `src/tcad_agent/web/static/ide.js`
- Modify: `src/tcad_agent/web/static/ide.css`
- Modify: `src/tcad_agent/web/static/ide-state.js`
- Modify: `tests/js/ide_navigation_guard.test.js`
- Test: `tests/unit/web/test_ide_javascript.py`
- Test: `tests/e2e/test_ide_shell.py`

**Interfaces:**
- Consumes: run, approval, conversation, and SSE endpoints from Task 5
- Produces: send, pause, resume, stop, approve, and deny controls with live activity rendering

- [ ] **Step 1: Write failing state and shell tests**

Test that a sent prompt creates one message and one run, tool events render once after SSE reconnection, pending approvals show exact tool and summary, buttons follow persisted state, and a final assistant message replaces the running indicator.

- [ ] **Step 2: Run tests and confirm the runtime controls are absent**

Run: `.venv/bin/pytest tests/unit/web/test_ide_javascript.py tests/e2e/test_ide_shell.py -q`

- [ ] **Step 3: Connect message submission to run creation**

Keep the prompt visible until both requests succeed. Disable duplicate sends while a run is active. Re-enable input in terminal states. Stream concrete actions and outputs without exposing chain-of-thought.

- [ ] **Step 4: Render approval and lifecycle controls**

Approval cards show tool, risk, exact canonical target or clipped command, and effect. Approve and deny send the current revision. Pause, resume, and stop act on the persisted run state.

- [ ] **Step 5: Render file changes, command outcomes, validation, and delegation**

Use compact scientific activity rows for file paths, exit codes, TCAD stages, validation status, subagent name, and task outcome. The conversation panel remains the primary prompt surface.

- [ ] **Step 6: Run browser and focused tests**

Run: `.venv/bin/pytest tests/unit/web/test_ide_javascript.py tests/e2e/test_ide_shell.py -q`

- [ ] **Step 7: Commit**

```bash
git add src/tcad_agent/web tests/js tests/unit/web/test_ide_javascript.py tests/e2e/test_ide_shell.py
git commit -m "feat: deliver live agent workflow in IDE"
```

### Task 7: End-to-end fixture, operations, and verification

**Files:**
- Modify: `README.md`
- Modify: `docs/operations/local-web-app.md`
- Modify: `tests/e2e/test_repl_fixture.py`
- Create: `tests/e2e/test_agentic_repl.py`

**Interfaces:**
- Consumes: complete agent runtime and `test-workspaces/pn-junction-research`
- Produces: reproducible local acceptance workflow and optional live Bedrock marker

- [ ] **Step 1: Write the end-to-end acceptance test**

The deterministic test opens the PN-junction repository, asks the scripted agent to diagnose and fix its intentionally failing validation, runs tests, delegates review, and asserts a clean evidence-backed final response. Add an opt-in `live_bedrock` case using the same repository and prompt without changing committed fixtures.

- [ ] **Step 2: Run the deterministic acceptance test and confirm the incomplete path**

Run: `.venv/bin/pytest tests/e2e/test_agentic_repl.py -q`

- [ ] **Step 3: Update product documentation**

Replace the obsolete claim that the production model never receives repository tools. Document the workspace grant, approval boundaries, tools, subagents, persistence, test prompt, DEVSIM path, Sentaurus boundary, current limitations, and exact launch command.

- [ ] **Step 4: Run the complete verification matrix**

```bash
.venv/bin/pytest -q
.venv/bin/ruff check src scripts evaluations tests
.venv/bin/mypy src
git diff --check
```

- [ ] **Step 5: Reinstall and perform browser QA**

Reinstall the local wheel, launch on `127.0.0.1`, open the test repository, start a deterministic task, observe tool and subagent events, exercise pause or resume and approval, inspect the resulting diff, and confirm no browser console errors at desktop and 768-pixel widths.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/operations tests/e2e
git commit -m "test: validate end-to-end agentic repository workflow"
```
