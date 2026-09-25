# Mature Agentic Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Turn Agent Kronig's existing repository UI into a responsive scientific agent workbench with structured activity, safe rendered chat, run-scoped changes, stable panes, and verifiable recovery behavior.

**Architecture:** Preserve the current OpenHands, SQLite, FastAPI, and SSE contracts. Add a bounded workspace-baseline service for honest run change attribution, pure JavaScript state helpers for deterministic UI behavior, and focused browser modules for layout and agent presentation. Keep the existing file viewer as the center-workspace foundation.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLite, vanilla JavaScript, CSS Grid, Server-Sent Events, pytest, Node or JavaScriptCore for pure JavaScript tests.

**Spec:** `docs/superpowers/specs/2026-09-25-mature-agentic-workbench-design.md`

## Global Constraints

- Treat `ExperimentSpec` as the simulator-neutral product contract.
- Never branch product behavior on a named device.
- Keep simulator syntax inside adapter packages.
- Refuse unsupported physics instead of approximating it silently.
- Preserve source, version, hash, compiler, simulator, and validation provenance.
- Never place proprietary Sentaurus documentation or credentials in the repository.
- Add behavior with a failing test first and run the complete suite before committing.
- The production UI must use a bundled NovAtom Labs logo, not a remote hotlink.
- The browser runtime must remain dependency-free and Linux-compatible.
- Pane separators are one visible pixel with a larger pointer target.
- Run-level permission grants expire at the end of a run.

## Review Focus

- A dirty repository starts a run: only changes after the captured baseline are attributed to the run. Task 1 tests this directly.
- A repository exceeds scan limits or contains a large binary: the API reports uncertainty instead of claiming an exact diff. Task 1 tests this directly.
- SSE reconnects replay persisted events: the presentation reducer rejects duplicates and preserves pending approvals. Task 3 tests this directly.
- The viewport becomes narrower while custom pane widths are stored: layout values are clamped and drawers replace compressed panes. Task 4 tests this directly.
- Assistant content contains raw HTML or unsafe links: Markdown displays text safely and rejects unsafe schemes. Task 3 tests this directly.

---

### Task 1: Run-Scoped Workspace Change Tracking

**Files:**
- Create: `src/tcad_agent/ide/changes.py`
- Modify: `src/tcad_agent/ide/models.py`
- Modify: `src/tcad_agent/ide/store.py`
- Test: `tests/unit/ide/test_changes.py`
- Test: `tests/unit/ide/test_store.py`

**Interfaces:**
- Produces: `WorkspaceBaseline`, `WorkspaceChange`, `WorkspaceChangeSet`, and `WorkspaceChangeTracker`.
- Produces: `SqliteIDEStore.save_run_baseline(run_id, baseline)` and `SqliteIDEStore.get_run_baseline(run_id)`.
- Consumes: existing `AgentRunRecord`, workspace roots, and strict Pydantic models.

- [x] **Step 1: Write failing model and tracker tests**

```python
def test_change_tracker_excludes_dirty_state_that_predates_run(tmp_path: Path) -> None:
    root = initialize_git_repo(tmp_path)
    tracked = root / "model.py"
    tracked.write_text("before run\n")
    baseline = WorkspaceChangeTracker().capture(root)
    tracked.write_text("before run\nafter run\n")
    changes = WorkspaceChangeTracker().compare(root, baseline)
    assert [(row.path, row.operation) for row in changes.files] == [("model.py", "modified")]
    assert changes.files[0].before_sha256 == baseline.files["model.py"].sha256

def test_change_tracker_marks_large_binary_comparison_uncertain(tmp_path: Path) -> None:
    target = tmp_path / "large.bin"
    target.write_bytes(b"x" * 64)
    tracker = WorkspaceChangeTracker(hash_limit=32)
    baseline = tracker.capture(tmp_path)
    target.write_bytes(b"y" * 64)
    changes = tracker.compare(tmp_path, baseline)
    assert changes.files[0].uncertain is True
    assert changes.files[0].diff is None
```

- [x] **Step 2: Run the focused tests and confirm missing contracts fail**

Run: `pytest tests/unit/ide/test_changes.py tests/unit/ide/test_store.py -q`

Expected: failure because the change models, tracker, and baseline store methods do not exist.

- [x] **Step 3: Add strict change contracts**

```python
class BaselineFile(StrictModel):
    path: str
    size: int = Field(ge=0)
    mtime_ns: int = Field(ge=0)
    sha256: str | None = None
    content: str | None = None

class WorkspaceBaseline(StrictModel):
    root: Path
    captured_at: datetime
    git_head: str | None = None
    git_branch: str | None = None
    truncated: bool = False
    files: dict[str, BaselineFile]

class WorkspaceChange(StrictModel):
    path: str
    operation: Literal["created", "modified", "deleted", "renamed"]
    previous_path: str | None = None
    before_sha256: str | None = None
    after_sha256: str | None = None
    additions: int | None = Field(default=None, ge=0)
    deletions: int | None = Field(default=None, ge=0)
    diff: str | None = None
    diff_truncated: bool = False
    uncertain: bool = False

class WorkspaceChangeSet(StrictModel):
    run_id: UUID | None = None
    baseline_captured_at: datetime
    generated_at: datetime
    baseline_truncated: bool
    files: tuple[WorkspaceChange, ...]
```

- [x] **Step 4: Implement bounded capture and comparison**

`WorkspaceChangeTracker.capture(root)` must skip `.git`, `.tcad-agent`, caches, symlinks, and protected credential paths. It records metadata for at most 5,000 files, hashes at most 1 MiB per file, stores UTF-8 baseline text subject to a 20 MiB total content budget, and marks the baseline truncated when limits are reached. `compare(root, baseline)` classifies create, modify, delete, and exact-hash rename operations. It uses `difflib.unified_diff` for stored UTF-8 text, caps each returned diff at 256 KiB with `diff_truncated=True`, and marks metadata-only changes uncertain.

- [x] **Step 5: Persist baselines in SQLite**

Add a `run_change_baselines` table with `run_id`, `baseline_json`, and `created_at`. Store and restore with strict model validation. Repeated writes for the same run are idempotent and never replace the original baseline.

- [x] **Step 6: Run focused tests and commit**

Run: `pytest tests/unit/ide/test_changes.py tests/unit/ide/test_store.py -q`

Commit: `feat: track run scoped workspace changes`

### Task 2: Baseline Lifecycle and Changes API

**Files:**
- Modify: `src/tcad_agent/agent/supervisor.py`
- Modify: `src/tcad_agent/web/ide_routes.py`
- Modify: `src/tcad_agent/web/app.py`
- Modify: `src/tcad_agent/ide/workspaces.py`
- Test: `tests/unit/agent/test_supervisor.py`
- Test: `tests/unit/web/test_ide_api.py`

**Interfaces:**
- Consumes: `WorkspaceChangeTracker.capture()` and `WorkspaceChangeTracker.compare()` from Task 1.
- Produces: `GET /api/runs/{run_id}/changes` returning `WorkspaceChangeSet`.
- Produces: a baseline captured after the run record exists and before any runtime tool executes.

- [x] **Step 1: Write failing supervisor and API tests**

```python
def test_start_captures_baseline_before_runtime_runs(services, runtime) -> None:
    supervisor = AgentSupervisor(services, runtime)
    run = supervisor.start(conversation.id, "repair and validate")
    assert services.store.get_run_baseline(run.id) is not None
    assert runtime.run_started_after_baseline is True

def test_run_changes_endpoint_excludes_preexisting_edits(web, repository) -> None:
    existing = repository / "existing.txt"
    existing.write_text("already dirty\n")
    run = start_run(web, repository)
    existing.write_text("already dirty\nagent line\n")
    response = web.get(f"/api/runs/{run['id']}/changes")
    assert response.status_code == 200
    assert response.json()["files"][0]["path"] == "existing.txt"
```

- [x] **Step 2: Run focused tests and verify baseline timing fails**

Run: `pytest tests/unit/agent/test_supervisor.py tests/unit/web/test_ide_api.py -q`

- [x] **Step 3: Wire the tracker through IDE services**

Add a `changes` service to the supervisor service protocol and `IDEServices`. In `AgentSupervisor.start`, create the run record, capture and persist the baseline, then create the runtime, send the prompt, transition the run, and launch its thread. If baseline capture fails, store an explicitly truncated empty baseline and emit a sanitized `change_baseline_warning` event rather than starting without an attribution boundary.

- [x] **Step 4: Add the read-only changes endpoint**

```python
@router.get("/runs/{run_id}/changes")
def run_changes(run_id: UUID) -> WorkspaceChangeSet:
    run = services.store.get_run(run_id)
    conversation = services.conversations.get(run.conversation_id)
    workspace = services.workspaces.get(conversation.workspace_id)
    baseline = services.store.get_run_baseline(run_id)
    return services.changes.compare(workspace.root, baseline).model_copy(
        update={"run_id": run_id}
    )
```

The endpoint performs no Git mutation and never returns content outside the workspace.

- [x] **Step 5: Run focused tests and commit**

Run: `pytest tests/unit/agent/test_supervisor.py tests/unit/web/test_ide_api.py -q`

Commit: `feat: expose honest per run change sets`

### Task 3: Pure Browser State, Event Reduction, and Safe Markdown

**Files:**
- Create: `src/tcad_agent/web/static/ide-events.js`
- Create: `src/tcad_agent/web/static/ide-markdown.js`
- Modify: `src/tcad_agent/web/static/ide-state.js`
- Create: `tests/js/ide_events.test.js`
- Create: `tests/js/ide_markdown.test.js`
- Modify: `tests/unit/web/test_ide_javascript.py`

**Interfaces:**
- Produces: `AgentKronigIDEEvents.createRunPresentation()` with `accept(event)`, `snapshot()`, and `reset()`.
- Produces: `AgentKronigMarkdown.render(container, source)` and `AgentKronigMarkdown.blocks(source)`.
- Consumes: current persisted and live `IDEEvent` objects without changing the SSE wire format.

- [x] **Step 1: Write failing event-reducer tests**

```javascript
const view = globalThis.AgentKronigIDEEvents.createRunPresentation();
view.accept(toolStarted(11, "call-1", "terminal", "Run focused tests"));
view.accept(toolCompleted(12, "call-1", "terminal", "2 passed"));
view.accept(toolCompleted(12, "call-1", "terminal", "2 passed"));
assertEqual(view.snapshot().steps.length, 1, "start and completion form one step");
assertEqual(view.snapshot().steps[0].status, "completed", "completion closes step");
assertEqual(view.snapshot().lastEventId, 12, "duplicate replay is ignored");
```

Include cases for subagent ownership, interrupted thinking, pending approvals, low-value event
suppression, and restored plus live events producing the same snapshot.

- [x] **Step 2: Write failing Markdown safety tests**

Test headings, lists, emphasis, inline code, fenced code, safe HTTP links, escaped raw HTML, and
rejected `javascript:` links. Rendering must use text nodes and constructed elements only.

- [x] **Step 3: Run focused JavaScript tests and verify failure**

Run: `pytest tests/unit/web/test_ide_javascript.py -q`

- [x] **Step 4: Implement the pure event reducer**

The reducer stores steps by `action_id` or stable fallback identity, maintains insertion order,
maps terminal events to run state, associates thinking summaries by item ID, and derives a
compact current operation. Unknown events are retained in `technicalEvents` without appearing
in the default activity list.

- [x] **Step 5: Implement the safe Markdown renderer**

Reuse the existing `markdownBlocks` behavior, add inline token rendering without raw HTML, and
share it with the file viewer. Allowed link schemes are `http:`, `https:`, and workspace-local
relative references. Links opening outside the application receive safe target attributes.

- [x] **Step 6: Run focused tests and commit**

Run: `pytest tests/unit/web/test_ide_javascript.py -q`

Commit: `feat: add deterministic agent presentation state`

### Task 4: Continuous Resizable Workbench Shell

**Files:**
- Create: `src/tcad_agent/web/static/ide-layout.js`
- Modify: `src/tcad_agent/web/templates/ide.html`
- Replace focused layout sections in: `src/tcad_agent/web/static/ide.css`
- Add: `src/tcad_agent/web/static/novatom-logo-horizontal-white.svg`
- Create: `tests/js/ide_layout.test.js`
- Modify: `tests/unit/web/test_ide_javascript.py`
- Modify: `tests/e2e/test_ide_shell.py`

**Interfaces:**
- Produces: `AgentKronigLayout.clampLayout(input)` and `AgentKronigLayout.createController(options)`.
- Consumes: workspace ID for preference keys and existing agent-panel open state.

- [x] **Step 1: Write failing geometry and shell tests**

```javascript
assertDeepEqual(
  AgentKronigLayout.clampLayout({viewport: 1180, explorer: 410, agent: 610}),
  {mode: "desktop", explorer: 360, agent: 320, center: 500},
  "stored widths are clamped while preserving the center minimum",
);
assertEqual(
  AgentKronigLayout.clampLayout({viewport: 680, explorer: 218, agent: 356}).mode,
  "narrow",
  "narrow widths use drawers",
);
```

The shell test must assert the official local logo, two ARIA separators, Chat, Activity, and
Changes tabs, and separate drawer controls. The JavaScript test must also assert bounded keyboard
increments, double-click reset values, corrupt stored-value rejection, and transition to drawers
before the center falls below 480 px.

- [x] **Step 2: Run focused tests and verify failure**

Run: `pytest tests/unit/web/test_ide_javascript.py tests/e2e/test_ide_shell.py -q`

- [x] **Step 3: Add and verify the official local logo asset**

Copy the official `novatom-logo-horizontal-white.svg` asset from `novatomlabs.com` into the
static package. Confirm the SVG contains no scripts, remote references, or credentials.

- [x] **Step 4: Implement the layout controller**

Use CSS custom properties `--explorer-width` and `--agent-width`. Pointer and keyboard resize
events update those values through `clampLayout`. Store valid desktop widths under
`agent-kronig.layout.<workspace-id>`. Double-click restores 218 px and 356 px. Media changes switch to
tablet or narrow drawer state and never keep a center smaller than 480 px.

- [x] **Step 5: Rebuild the page shell and visual system**

Create a contiguous three-pane grid with one shared border, 31 px pane headers, 10 px and 12 px
content tokens, compact NovAtom and Agent Kronig branding, restrained state colors, and no gradients,
glow, floating primary cards, or decorative chat bubbles. Ensure pane-specific selectors do not
inherit page container margins or padding.

- [x] **Step 6: Run focused tests and commit**

Run: `pytest tests/unit/web/test_ide_javascript.py tests/e2e/test_ide_shell.py -q`

Commit: `feat: build continuous resizable research workbench`

### Task 5: Structured Chat, Activity, Permissions, and Changes

**Files:**
- Create: `src/tcad_agent/web/static/ide-agent.js`
- Create: `src/tcad_agent/web/static/ide-changes.js`
- Modify: `src/tcad_agent/web/static/ide.js`
- Modify: `src/tcad_agent/web/templates/ide.html`
- Modify: `src/tcad_agent/web/static/ide.css`
- Create: `tests/js/ide_agent.test.js`
- Create: `tests/js/ide_changes.test.js`
- Modify: `tests/unit/web/test_ide_javascript.py`
- Modify: `tests/e2e/test_ide_shell.py`

**Interfaces:**
- Consumes: presentation snapshots from `AgentKronigIDEEvents`.
- Consumes: `GET /api/runs/{run_id}/changes`.
- Produces: tab rendering, step expansion, file and diff navigation callbacks, completion focus,
  and plain-language permission cards.

- [x] **Step 1: Write failing view-model and DOM-contract tests**

Test that lifecycle noise is absent from default Activity, one tool call produces one expandable
step, a subagent nests under its owner, a completed run creates a structured summary, and a
failed run retains partial evidence. Test that permission cards include explanation, target,
risk, technical details, Deny, Approve, and Approve all like this for grantable categories.

- [x] **Step 2: Write failing changes-view tests**

```javascript
const rows = AgentKronigChanges.toRows(changeSet);
assertEqual(rows[0].label, "src/physics.py");
assertEqual(rows[0].delta, "+8 −3");
assertEqual(rows[0].uncertain, false);
```

Include created, deleted, renamed, binary, uncertain, empty, and unavailable cases.

- [x] **Step 3: Run focused tests and verify failure**

Run: `pytest tests/unit/web/test_ide_javascript.py tests/e2e/test_ide_shell.py -q`

- [x] **Step 4: Render assistant messages as safe technical notes**

Replace plain `textContent` message bodies with `AgentKronigMarkdown.render`. Preserve authorship and
timestamps. When a final assistant message arrives, scroll its top into view without forcing
the activity timeline to its bottom.

- [x] **Step 5: Replace raw activity appends with presentation rendering**

Feed restored and live events through one reducer. Render grouped steps, derived operational
status, subagents, durations, affected files, collapsed commands, output, and technical events. Never persist or render raw provider reasoning. Keep
pause, resume, stop, reconnection, and refresh behavior intact.

- [x] **Step 6: Implement Chat, Activity, and Changes tabs**

Tabs retain independent scroll positions. Pending approvals remain visible in Chat and produce
an Activity marker. Changes refresh after file-affecting tools and terminal run states. File
clicks use the existing viewer; diff clicks open a dedicated diff surface in the center pane.

- [x] **Step 7: Implement completion and failure reports**

Completion shows changed files, validation evidence, artifacts, warnings, and suggested next
actions available from actual events and the change set. Failure shows the failed step, last
successful step, retained output, affected files, and retry or inspect actions.

- [x] **Step 8: Run focused tests and commit**

Run: `pytest tests/unit/web/test_ide_javascript.py tests/e2e/test_ide_shell.py tests/unit/web/test_ide_api.py -q`

Commit: `feat: present agent work as structured scientific activity`

### Task 6: End-to-End Verification and Product Documentation

**Files:**
- Modify: `tests/e2e/test_agentic_repl.py`
- Modify: `README.md`
- Modify: `INSTALL.md` if installation details change
- Modify: `docs/superpowers/plans/2026-09-25-mature-agentic-workbench.md` to check completed tasks

**Interfaces:**
- Consumes: all previous tasks.
- Produces: one reproducible acceptance path and final verified branch state.

- [x] **Step 1: Add a failing acceptance test for the complete run evidence**

Extend the deterministic repository runtime scenario to assert baseline creation, terminal-made
changes, grouped activity, final `WorkspaceChangeSet`, and unchanged simulator-neutral
execution boundaries.

- [x] **Step 2: Run the focused end-to-end scenario**

Run: `pytest tests/e2e/test_agentic_repl.py -q`

- [x] **Step 3: Update user-facing documentation**

Document the three panes, Chat and Activity and Changes views, resizers, drawers, safe Markdown,
permission behavior, run-scoped attribution, and the exact realistic test-workspace walkthrough.
Do not claim interactive TTY, collaboration, automatic Git mutation, or unsupported simulator
capabilities.

- [x] **Step 4: Run static verification**

Run:

```bash
ruff check .
mypy src/tcad_agent
pytest tests/unit/web tests/unit/ide tests/unit/agent tests/e2e/test_ide_shell.py tests/e2e/test_agentic_repl.py -q
```

- [x] **Step 5: Run the complete test suite**

Run: `pytest -q`

Expected: all installed, non-environment-dependent tests pass. Existing simulator or live-model
tests may skip only under their documented markers or missing external dependencies.

- [x] **Step 6: Exercise the live UI**

Start Agent Kronig locally, open the realistic test repository, create a conversation, run a safe
read-only prompt, inspect Chat and Activity and Changes, test both dividers at desktop width,
test tablet and narrow drawer modes, open and edit a file, and verify that completion begins at
the top of its report. Capture console errors and fix every product-owned error.

- [x] **Step 7: Commit the verified integration**

Commit: `docs: document mature agentic workbench workflow`

- [x] **Step 8: Review the complete branch diff**

Run:

```bash
git diff --check main...HEAD
git status --short
git log --oneline main..HEAD
```

Confirm that no credentials, proprietary Sentaurus content, temporary mockups, runtime data, or
unrelated user files are included.
