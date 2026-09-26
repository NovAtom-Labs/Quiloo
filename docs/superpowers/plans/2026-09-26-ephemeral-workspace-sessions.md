# Ephemeral Workspace Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace persistent repository conversations with one process-scoped workspace session that is destroyed when Agent Kronig closes or changes repository.

**Architecture:** The desktop backend will create a locked, allowlisted temporary runtime root for the current process while leaving settings and credentials in the persistent desktop data directory. Existing conversation-oriented execution primitives remain internal, but a new single-session service and workspace-scoped API become the product contract. The frontend binds directly to that workspace session and removes all conversation history, selection, creation, restoration, and conversation-specific routing.

**Tech Stack:** Python 3.13, FastAPI, SQLite, OpenHands SDK, vanilla JavaScript, Jinja2, Electron, Node test runner, pytest, Ruff

**Spec:** `docs/superpowers/specs/2026-09-26-ephemeral-workspace-sessions-design.md`

## Global Constraints

- `ExperimentSpec` remains the simulator-neutral product contract.
- Never branch product behavior on a named device.
- Keep simulator syntax inside its adapter package.
- Refuse unsupported physics instead of approximating it silently.
- Preserve source, version, hash, compiler, simulator, and validation provenance in repository artifacts.
- Never place proprietary Sentaurus documentation or credentials in repository or session storage.
- Repository files, simulator outputs, validation reports, settings, and protected credentials must survive session cleanup.
- Messages, runs, approvals, events, change baselines, run manifests, permission grants, and OpenHands state must not survive a desktop process.
- There is at most one workspace session and one live workspace writer in a desktop process.
- Behavior must be identical on Linux, macOS, and Windows.
- Add each behavior with a failing test first and run the complete suite before the final commit.
- Do not use em dashes in product copy or documentation.

## Review Focus

- A symlink or malformed legacy path inside the application data directory must never let cleanup delete outside that directory. Task 1 adds explicit containment and symlink tests.
- A crash between session-root creation and cleanup must leave data that the next startup removes before serving requests. Task 1 adds interrupted-startup recovery coverage.
- Reopening the same workspace must be idempotent, while switching repositories during a live run must fail without discarding either repository session or files. Task 2 adds both cases.
- A delayed response or SSE frame from a released workspace must never render in the newly opened workspace. Task 4 extends route and request-generation tests.
- Existing persistent memory may be locked, incomplete, or missing during migration. Task 1 tests missing files, SQLite sidecars, and sanitized fail-closed behavior.

---

### Task 1: Desktop Session Storage and Legacy Cleanup

**Files:**
- Create: `src/tcad_agent/desktop/session_storage.py`
- Modify: `src/tcad_agent/desktop/server.py`
- Test: `tests/unit/desktop/test_session_storage.py`
- Test: `tests/unit/desktop/test_server.py`

**Interfaces:**
- Consumes: `DesktopLaunchConfig.data_dir: Path` and the existing `DataDirectoryLock` ownership guarantee.
- Produces: `DesktopSessionStorage.prepare(data_dir: Path) -> DesktopSessionStorage`, `.runtime_root: Path`, `.cleanup() -> None`, and the one-time legacy cleanup marker `repository-memory-removed-v1`.

- [ ] **Step 1: Write failing session-storage tests**

Add tests named:

- `test_prepare_creates_unique_runtime_root_beneath_session_area`
- `test_cleanup_removes_only_the_current_runtime_root`
- `test_prepare_removes_stale_runtime_roots_after_lock_acquisition`
- `test_prepare_rejects_symlinked_session_area_that_escapes_data_dir`
- `test_legacy_cleanup_removes_ide_database_sidecars_and_openhands_memory`
- `test_legacy_cleanup_is_idempotent_when_paths_are_missing`
- `test_legacy_cleanup_never_removes_settings_credentials_or_repository_files`
- `test_legacy_cleanup_failure_is_sanitized_and_stops_startup`

Assert exact allowlisted legacy names: `ide.sqlite3`, `ide.sqlite3-wal`, `ide.sqlite3-shm`, and `openhands`. Assert that `settings.json`, `secrets.bin`, `requests.sqlite3`, and an external repository sentinel remain.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/unit/desktop/test_session_storage.py -q`

Expected: FAIL because `tcad_agent.desktop.session_storage` does not exist.

- [ ] **Step 3: Implement `DesktopSessionStorage`**

In `src/tcad_agent/desktop/session_storage.py`, add:

- `class DesktopSessionStorageError(RuntimeError)`
- `@dataclass class DesktopSessionStorage`
- `@classmethod prepare(cls, data_dir: Path) -> DesktopSessionStorage`
- `cleanup(self) -> None`

Use a fixed `sessions` child under the resolved, locked data directory and a random process root below it. Validate every cleanup target with `Path.resolve()` containment before deletion. Reject symlinked session or legacy targets. Create the migration marker only after all allowlisted legacy paths are absent.

- [ ] **Step 4: Run session-storage tests and verify GREEN**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/unit/desktop/test_session_storage.py -q`

Expected: all session-storage tests PASS.

- [ ] **Step 5: Write failing desktop server lifecycle tests**

Add tests proving `serve_desktop` prepares storage only after the data-directory lock is held, passes the temporary runtime root into application construction, and calls cleanup after normal server exit and startup failure.

- [ ] **Step 6: Run server tests and verify RED**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/unit/desktop/test_server.py -q`

Expected: FAIL because `create_desktop_app` still roots services in `config.data_dir` and `serve_desktop` does not own session storage.

- [ ] **Step 7: Integrate session storage with the desktop server**

Change the signature to `create_desktop_app(config: DesktopLaunchConfig, runtime_root: Path) -> FastAPI`. Set `TCAD_WORKSPACE` to `runtime_root`, construct IDE and OpenHands services there, and keep settings and credentials rooted at `config.data_dir`. In `serve_desktop`, prepare and clean session storage inside `DataDirectoryLock` and outside the Uvicorn lifetime.

- [ ] **Step 8: Run Task 1 verification**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/unit/desktop/test_session_storage.py tests/unit/desktop/test_server.py -q`

Expected: all Task 1 tests PASS.

- [ ] **Step 9: Commit Task 1**

```bash
git add src/tcad_agent/desktop/session_storage.py src/tcad_agent/desktop/server.py tests/unit/desktop/test_session_storage.py tests/unit/desktop/test_server.py
git commit -m "Use ephemeral desktop session storage"
```

### Task 2: Single Workspace Session Service

**Files:**
- Create: `src/tcad_agent/ide/sessions.py`
- Modify: `src/tcad_agent/ide/models.py`
- Modify: `src/tcad_agent/ide/store.py`
- Modify: `src/tcad_agent/agent/supervisor.py`
- Test: `tests/unit/ide/test_sessions.py`
- Test: `tests/unit/ide/test_store.py`
- Test: `tests/unit/agent/test_supervisor.py`

**Interfaces:**
- Consumes: Task 1's process-scoped runtime root, `WorkspaceManager`, `ConversationService`, `SqliteIDEStore`, and `AgentSupervisor` live-run state.
- Produces: `WorkspaceSessionRecord`, `WorkspaceSessionBusyError`, `WorkspaceSessionService.open(workspace_id: UUID) -> WorkspaceSessionRecord`, `.current() -> WorkspaceSessionRecord | None`, `.release() -> None`, and `.shutdown() -> None`.

- [ ] **Step 1: Write failing store-deletion tests**

Add `test_delete_conversation_tree_removes_only_owned_session_records`. Create two workspaces with messages, events, runs, approvals, grants, baselines, and manifests. Delete one internal conversation tree and assert every owned row is gone while the other workspace and repository files remain.

- [ ] **Step 2: Run store test and verify RED**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/unit/ide/test_store.py::test_delete_conversation_tree_removes_only_owned_session_records -q`

Expected: FAIL because `SqliteIDEStore.delete_conversation_tree` does not exist.

- [ ] **Step 3: Implement bounded internal session deletion**

Add `SqliteIDEStore.delete_conversation_tree(conversation_id: UUID) -> None`. Use one `BEGIN IMMEDIATE` transaction and explicit child-first deletes. Do not delete workspace rows or repository content.

- [ ] **Step 4: Run store test and verify GREEN**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/unit/ide/test_store.py::test_delete_conversation_tree_removes_only_owned_session_records -q`

Expected: PASS.

- [ ] **Step 5: Write failing workspace-session service tests**

Add tests named:

- `test_open_creates_one_untitled_internal_session_for_workspace`
- `test_open_same_workspace_returns_current_session`
- `test_open_different_workspace_releases_previous_session_tree`
- `test_open_different_workspace_refuses_while_live_run_exists`
- `test_release_refuses_while_live_run_exists`
- `test_release_clears_terminal_session_and_openhands_state`
- `test_shutdown_denies_approvals_cancels_nonterminal_run_and_clears_state`
- `test_release_preserves_repository_files_and_generated_artifacts`

- [ ] **Step 6: Run session-service tests and verify RED**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/unit/ide/test_sessions.py -q`

Expected: FAIL because `WorkspaceSessionService` does not exist.

- [ ] **Step 7: Implement the workspace-session service**

Add `WorkspaceSessionRecord` with `id: UUID`, `workspace_id: UUID`, and `created_at: datetime`. Implement `WorkspaceSessionService` as the only owner of the process's current internal conversation. `open` and `release` must reject a repository change while a live run exists. `shutdown` is the distinct desktop-lifecycle operation that uses `AgentSupervisor.stop` to cancel live work and deny pending approvals before deletion. Use `SqliteIDEStore.delete_conversation_tree` for released state and a contained runtime-directory cleanup for the internal OpenHands UUID.

Expose a read-only `AgentSupervisor.active_run_for_workspace(workspace_id: UUID) -> AgentRunRecord | None` so the service does not duplicate active-state policy.

- [ ] **Step 8: Run Task 2 verification**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/unit/ide/test_sessions.py tests/unit/ide/test_store.py tests/unit/agent/test_supervisor.py -q`

Expected: all Task 2 tests PASS.

- [ ] **Step 9: Commit Task 2**

```bash
git add src/tcad_agent/ide/sessions.py src/tcad_agent/ide/models.py src/tcad_agent/ide/store.py src/tcad_agent/agent/supervisor.py tests/unit/ide/test_sessions.py tests/unit/ide/test_store.py tests/unit/agent/test_supervisor.py
git commit -m "Add single ephemeral workspace sessions"
```

### Task 3: Workspace-Scoped Agent API

**Files:**
- Modify: `src/tcad_agent/web/ide_routes.py`
- Modify: `src/tcad_agent/web/schemas.py`
- Modify: `src/tcad_agent/web/app.py`
- Test: `tests/unit/web/test_ide_api.py`
- Test: `tests/unit/web/test_api.py`
- Test: `tests/unit/desktop/test_server.py`

**Interfaces:**
- Consumes: Task 2's `WorkspaceSessionService` and `WorkspaceSessionRecord`.
- Produces: `/api/workspaces/{workspace_id}/session`, `/session/messages`, `/session/runs`, `/session/runs/active`, `/session/approvals`, and `/session/events` endpoints plus existing run-control, approval-decision, change, file, and repository endpoints.

- [ ] **Step 1: Write failing API contract tests**

Add tests proving:

- `POST /api/workspaces/{workspace_id}/session` is idempotent;
- messages and runs are created through workspace-session routes;
- approvals and SSE events are readable only for the current workspace session;
- opening a second workspace returns `409 workspace_session_busy` during a live run;
- opening a second workspace after terminal completion releases the first session;
- conversation list, creation, detail, message, run, approval-list, event, and conversation-page routes return `404`;
- `/workspaces/{workspace_id}/conversations/{conversation_id}` returns `404` rather than the IDE shell.

Add desktop lifecycle tests proving that authenticated `POST /api/desktop/prepare-shutdown` cancels the live workspace session, denies unresolved approvals, and returns ready after agent work becomes terminal. Preserve the refusal behavior when non-agent simulation work cannot be safely cancelled.

- [ ] **Step 2: Run API tests and verify RED**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/unit/web/test_ide_api.py tests/unit/web/test_api.py -q`

Expected: FAIL because workspace-session routes do not exist and conversation routes remain public.

- [ ] **Step 3: Add the session service to `IDEServices`**

Extend `IDEServices` with `sessions: WorkspaceSessionService`. Construct it in `build_default_ide_services` after the store, conversation service, and event feed exist. Pass the active supervisor into the service after supervisor construction through an explicit `bind_supervisor(supervisor: AgentSupervisor) -> None` method.

- [ ] **Step 4: Replace the public conversation API**

Move message, run-start, active-run, approval-list, and event-stream behavior behind workspace-session routes. Resolve the internal conversation UUID exclusively through `WorkspaceSessionService`. Remove conversation-management routes and the conversation page route. Preserve sanitized error contracts and optimistic revision checks.

Change the authenticated desktop shutdown route to call `WorkspaceSessionService.shutdown()` before evaluating the remaining shutdown gate. This makes closing Agent Kronig cancel its temporary agent session while continuing to protect any separate simulation operation that cannot be safely interrupted.

- [ ] **Step 5: Run Task 3 verification**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/unit/web/test_ide_api.py tests/unit/web/test_api.py tests/unit/desktop/test_server.py tests/e2e/test_agentic_repl.py -q`

Expected: all Task 3 tests PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/tcad_agent/web/ide_routes.py src/tcad_agent/web/schemas.py src/tcad_agent/web/app.py tests/unit/web/test_ide_api.py tests/unit/web/test_api.py tests/unit/desktop/test_server.py tests/e2e/test_agentic_repl.py
git commit -m "Expose workspace scoped agent sessions"
```

### Task 4: Remove Conversation Memory from the Frontend

**Files:**
- Modify: `src/tcad_agent/web/templates/ide.html`
- Modify: `src/tcad_agent/web/static/ide.js`
- Modify: `src/tcad_agent/web/static/ide.css`
- Modify: `src/tcad_agent/web/static/ide-state.js`
- Modify: `src/tcad_agent/web/static/ide-events.js`
- Test: `tests/unit/web/test_ide_javascript.py`
- Test: `tests/js/ide_navigation_guard.test.js`
- Test: `tests/js/ide_events.test.js`
- Test: `tests/e2e/test_ide_shell.py`

**Interfaces:**
- Consumes: Task 3's workspace-session API and workspace-only route.
- Produces: one workspace-bound Chat view with no user-visible conversation concept.

- [ ] **Step 1: Write failing template and route tests**

Assert that the rendered IDE contains none of:

- `conversation-select`;
- `create-conversation`;
- `conversation-dialog`;
- `conversation-title-input`;
- `Start a repository conversation`;
- `Select a conversation`;
- `New conversation`;
- conversation-specific URL parsing.

Assert that the workspace page contains a compact session-state heading, the current-session message list, and the enabled message composer after session creation.

- [ ] **Step 2: Run frontend structure tests and verify RED**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/unit/web/test_ide_javascript.py tests/e2e/test_ide_shell.py -q`

Expected: FAIL because conversation controls and routing remain.

- [ ] **Step 3: Remove conversation controls and styles**

Delete the selector, creation button, creation dialog, title input, and their CSS. Replace the header with a semantic session-state label and retain only Refresh, Close, and applicable run controls. Change empty copy to `Describe the task for this repository.`

- [ ] **Step 4: Rebind frontend state to the workspace session**

Remove `conversationId` from route parsing, navigation, submission recovery, refresh coordination, and stale-response guards. On workspace load, call `POST /api/workspaces/{workspace_id}/session`, bind messages, active run, approvals, events, activity, and changes through Task 3 routes, and keep the returned session UUID only as a request-generation discriminator.

- [ ] **Step 5: Add stale-session frontend tests**

Update JavaScript tests to prove that delayed message responses, approval refreshes, and SSE events carrying the released session key are ignored after opening another workspace. Prove that a new workspace starts with an empty message list and no selected run.

- [ ] **Step 6: Run Task 4 verification**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/unit/web/test_ide_javascript.py tests/e2e/test_ide_shell.py -q`

Expected: all frontend tests PASS and no conversation UI strings remain.

- [ ] **Step 7: Commit Task 4**

```bash
git add src/tcad_agent/web/templates/ide.html src/tcad_agent/web/static/ide.js src/tcad_agent/web/static/ide.css src/tcad_agent/web/static/ide-state.js src/tcad_agent/web/static/ide-events.js tests/unit/web/test_ide_javascript.py tests/js/ide_navigation_guard.test.js tests/js/ide_events.test.js tests/e2e/test_ide_shell.py
git commit -m "Remove repository conversation memory UI"
```

### Task 5: End-to-End Lifecycle, Documentation, and Final Verification

**Files:**
- Modify: `tests/e2e/test_agentic_repl.py`
- Create: `tests/e2e/test_ephemeral_workspace_session.py`
- Modify: `README.md`
- Modify: `INSTALLATION.md`
- Modify: `docs/architecture.md`
- Modify: `docs/operations/desktop-application.md`

**Interfaces:**
- Consumes: Tasks 1 through 4 as one desktop lifecycle.
- Produces: verified cross-process behavior and user-facing documentation that contains no repository-memory claims.

- [ ] **Step 1: Write failing end-to-end lifecycle tests**

Add tests named:

- `test_restart_discards_messages_runs_approvals_events_and_openhands_state`
- `test_restart_preserves_repository_artifacts_settings_and_credentials`
- `test_crash_recovery_removes_stale_session_before_new_workspace_opens`
- `test_switching_repository_after_completed_run_clears_chat_and_activity`
- `test_switching_repository_during_live_run_is_rejected_without_file_loss`

Use two application instances with the same persistent desktop data directory and separate temporary backend lifetimes. Assert no conversation or run from the first instance is addressable by the second.

- [ ] **Step 2: Run lifecycle tests and verify RED**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/e2e/test_ephemeral_workspace_session.py -q`

Expected: FAIL until every cross-task lifecycle boundary is wired correctly.

- [ ] **Step 3: Complete lifecycle wiring**

Fix only integration gaps exposed by Step 2. Do not add persistence fallbacks. Ensure shutdown and startup cleanup close database handles before deletion and preserve repository artifacts.

- [ ] **Step 4: Update product and installation documentation**

Replace persistent-conversation claims with the exact session boundary. Document that chat history is intentionally temporary, repository artifacts persist, restart begins clean, and future repository memory is out of scope.

- [ ] **Step 5: Run documentation and lifecycle verification**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/e2e/test_ephemeral_workspace_session.py tests/e2e/test_agentic_repl.py tests/e2e/test_ide_shell.py -q`

Run: `rg -n "persistent research session|conversation history|restore.*conversation|repository memory" README.md INSTALLATION.md docs src/tcad_agent/web/templates src/tcad_agent/web/static`

Expected: tests PASS; search returns only the approved design, implementation plan, migration documentation, and explicit statements that repository memory is not retained.

- [ ] **Step 6: Run complete verification**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q`

Expected: all Python tests PASS with only documented environment skips.

Run: `.venv/bin/ruff check .`

Expected: `All checks passed!`

Run: `cd desktop && pnpm test`

Expected: all desktop tests PASS. If the shell cannot resolve `node`, run the same suite with the Electron binary under `ELECTRON_RUN_AS_NODE=1`.

Run: `git diff --check`

Expected: no output.

- [ ] **Step 7: Commit Task 5**

```bash
git add tests/e2e/test_agentic_repl.py tests/e2e/test_ephemeral_workspace_session.py README.md INSTALLATION.md docs/architecture.md docs/operations/desktop-application.md
git commit -m "Document ephemeral workspace sessions"
```
