# Mature Agentic Workbench Design

## 1. Objective

Quiloo will present its existing repository agent as a mature scientific workbench. A
researcher must be able to keep the repository, current file, agent conversation, execution
state, permissions, changes, and validation evidence visible without reading a raw event log.

The workbench must feel like engineering software rather than a marketing dashboard or a chat
application. It uses stable geometry, compact technical language, restrained color, and
evidence-backed status. The agent remains prominent without displacing the repository and file
workspace.

This design changes presentation and run evidence. It does not replace the current OpenHands
runtime, simulator-neutral TCAD architecture, permission policy, file APIs, or Server-Sent
Events transport.

## 2. Success Criteria

The completed work must let a researcher:

1. Resize the explorer and agent panes without creating uneven gaps or unusable center space.
2. Continue working at narrower widths through drawers instead of compressed three-pane
   layouts.
3. Understand what an active agent is doing without reading every lifecycle event.
4. Inspect the technical command, output, affected files, provenance, and duration when needed.
5. See concise operational reasoning without exposing or depending on private model
   chain-of-thought.
6. Review changes attributable to the current run, including changes made through terminal
   commands.
7. Open an affected file or diff directly from agent activity.
8. Understand permission requests in plain language while retaining exact technical details.
9. Recover from stream interruptions without duplicate activity or lost approvals.
10. Read correctly rendered assistant Markdown and a structured completion or failure report.

## 3. Product Principles

### 3.1 Scientific workbench, not chat product

Files and evidence are first-class. Messages read as technical notes with clear authorship,
not decorative chat bubbles. Empty states, transitions, and controls remain compact.

### 3.2 One continuous surface

The desktop interface is a contiguous explorer, workspace, and agent grid. Adjacent panes share
one visible separator. There are no independent cards or arbitrary gutters between primary
panes.

### 3.3 Progressive detail

The default view shows the current objective, meaningful execution steps, and outcome. Raw
commands, tool output, provider details, and provenance remain available through expansion.

### 3.4 Evidence over animation

Color indicates state, risk, validation, and change. It is not used decoratively. A progress
indicator must name the current operation. Generic indefinite messages such as "Working in the
repository" are not sufficient.

### 3.5 Honest attribution

Quiloo must distinguish changes made during the current run from changes that already existed
in the workspace. It must not silently claim ownership of unrelated modifications.

## 4. Visual and Spatial Model

### 4.1 Brand treatment

The application header uses the official NovAtom Labs horizontal wordmark as a bundled local
asset. Quiloo appears beside it as the product name. Production must not hotlink the public
website or depend on external availability for branding.

### 4.2 Desktop grid

The default desktop layout is:

```text
Explorer, 218 px | File workspace, flexible | Agent, 356 px
```

The geometry contract is:

- Explorer minimum 196 px and maximum 360 px.
- Agent minimum 320 px and maximum 520 px.
- Center workspace minimum 480 px.
- One 1 px visual separator between adjacent panes.
- Each separator has an invisible 9 px pointer target centered on the visible rule.
- Pane headers use one shared height token, initially 31 px.
- Primary pane content uses shared 10 px and 12 px inset tokens.
- Resizing changes pane width only. It never changes internal padding or adds margins.

The last desktop widths are stored per workspace in browser-local preferences. Double-clicking
a divider restores its default width. Keyboard-operable separators expose appropriate ARIA
roles and update in bounded increments.

### 4.3 Responsive behavior

The system selects a responsive mode from available center width rather than allowing all three
panes to collapse.

- Wide desktop: all three panes are visible and resizable.
- Tablet: the explorer becomes a left drawer. The agent may remain a right pane while the
  center can retain at least 480 px.
- Narrow: both explorer and agent become full-height drawers. Only one drawer is open at a
  time, and the center workspace remains the base surface.
- File headers may wrap into two controlled rows. Their actions must not overflow invisibly.

## 5. Workspace and Agent Views

### 5.1 Center workspace

The existing file viewer remains the foundation for source, Markdown, JSON, delimited data,
images, PDFs, and binary metadata. It continues to support editing where the current API marks
a file editable.

The center workspace adds or standardizes:

- File tabs with dirty and agent-modified indicators.
- A diff view selectable from the Changes panel.
- Stable file action placement at narrow widths.
- Direct navigation from activity and validation evidence.
- Clear preview, source, and edit modes without duplicating file content.

### 5.2 Agent tabs

The right pane contains three persistent tabs.

#### Chat

Chat contains user prompts, rendered assistant Markdown, approval requests, concise run
summaries, and completion reports. Messages use technical-document typography rather than
bubbles.

#### Activity

Activity shows a grouped chronological execution timeline. The primary phases are Inspect,
Plan, Edit, Execute, Validate, and Report. Phases appear only when supported by actual events.
Low-value lifecycle events are hidden by default but remain available in an optional technical
event view.

Each execution step may show:

- Status and duration.
- Tool or subagent identity.
- Plain-language action summary.
- Command or operation details.
- Affected files and paths.
- Collapsed output with explicit truncation state.
- Simulator, compiler, model, and validation provenance when applicable.

Tool start and completion events are presented as one step. Clicking a file reference opens the
file. Clicking a modified file opens the relevant diff when one exists.

#### Changes

Changes lists files changed during the active or selected run. It includes operation type, line
counts, validation state, and attribution. Selecting a file opens its diff in the center
workspace. A workspace-wide view may also show pre-existing changes, but those must be labelled
separately.

### 5.3 Operational reasoning summary

During a run, Quiloo may show a short user-facing reasoning summary containing:

- Current objective.
- Working hypothesis.
- Evidence being examined.
- Current action.
- Next intended action.

This is an operational explanation, not a raw model chain-of-thought transcript. It is bounded
in height, collapsible, and summarized when a phase completes. If a reasoning stream is
interrupted, the UI marks the summary as interrupted rather than leaving it live indefinitely.

### 5.4 Subagents

Subagent work appears under the execution step that created it. Each subagent receives one
compact row with its assignment, state, elapsed time, and outcome. Expanded details show its
tool activity and evidence. Multiple subagents may work concurrently, but their output is
grouped by owner and never interleaved as an unreadable raw stream.

## 6. Run and Permission Interaction

### 6.1 Run header

The run header shows:

- Task title.
- Current phase and operation.
- Run state.
- Elapsed time.
- Files changed.
- Validation progress.

Pause, resume, and stop remain available according to the existing run state machine.

### 6.2 Permission requests

Permission requests remain visible until resolved, including during stream reconnection. Each
request contains:

- A plain-language explanation of what the agent wants to do and why.
- The affected path, command, external host, or resource.
- Risk and reversibility.
- Expandable technical details with the exact tool and arguments.
- Deny.
- Approve this action.
- Approve all actions in the same grantable permission category for this run.

Run-level grants expire when the run ends. Existing restrictions for complex shell commands and
unrecognized actions remain unchanged unless a separate security design changes them.

### 6.3 Completion and failure

A successful completion report contains:

- Outcome summary.
- Changed files.
- Commands and simulations executed.
- Validation results.
- Generated artifacts.
- Warnings and unsupported requests.
- Suggested next actions.

The view scrolls to the beginning of the new completion report, not to an arbitrary point at the
bottom of a long activity stream.

A failure report contains the failed phase, failed operation, last successful phase, available
output, affected files, and recovery options. Failure must not erase partial evidence.

## 7. Technical Architecture

### 7.1 Event presentation pipeline

The persisted event ledger and live SSE stream remain the source of truth.

```text
Persisted events plus live SSE
            |
            v
Event deduplicator and run-state reducer
            |
            v
Presentation model
            |
            +-- Chat
            +-- Activity
            +-- Changes
```

The reducer pairs related start and completion events by stable action identity, associates
subagent ownership, closes interrupted reasoning, derives phase state, and produces one
presentation model for both restored and live conversations. DOM rendering must not contain the
state transition logic.

The reducer must preserve the existing event contract. Additive event fields may be introduced
when required, but the frontend must tolerate older persisted events that lack them.

### 7.2 Frontend modules

The current large IDE script will be separated along responsibility boundaries:

- `ide-layout.js`: pane geometry, drawers, responsive transitions, and stored preferences.
- `ide-events.js`: SSE lifecycle, cursor recovery, deduplication, and presentation reduction.
- `ide-agent.js`: Chat, Activity, run summaries, reasoning summaries, and permissions.
- `ide-changes.js`: change manifests, diffs, validation links, and file navigation.
- `file-viewer.js`: existing file preview and editing behavior, extended only where shared
  rendering is required.

The page shell keeps semantic landmarks and stable element identifiers. Styling uses a compact
token set for pane sizes, header heights, borders, spacing, typography, and state colors.

### 7.3 Markdown safety

Assistant Markdown rendering reuses and extends the existing block parser rather than assigning
untrusted HTML to the DOM. Text is inserted with text nodes. Links accept only explicitly
allowed schemes. Raw HTML remains escaped. Code fences, headings, paragraphs, lists, quotes,
inline code, emphasis, and safe links are sufficient for the first implementation.

### 7.4 Run-scoped change manifest

Before a write-capable run begins, Quiloo records a read-only workspace baseline. For Git
repositories this includes HEAD identity, branch, staged state, unstaged state, untracked paths,
and content hashes needed to distinguish pre-existing modifications. For non-Git repositories,
Quiloo scans the workspace subject to explicit file-count and file-size limits. It records path,
size, modification time, and a content hash for files within the hashing limit. Larger files use
metadata-only comparison and are labelled as uncertain if they change. Ignored runtime data and
repository metadata are excluded by a defined policy.

After relevant tool completions and at terminal run states, Quiloo computes a run change
manifest. The manifest contains:

- Relative path.
- Created, modified, deleted, or renamed operation.
- Before and after content hashes when available.
- Added and removed line counts for text files.
- Tool and subagent attribution when known.
- Validation evidence linked to the path.
- Explicit uncertainty when an operation cannot be attributed safely.

This comparison is read-only. It must not stage files, reset user work, or alter Git state.
Repository path containment rules apply to every diff and content read.

### 7.5 Branding asset

The official NovAtom Labs white horizontal SVG from the company website is copied into the
repository as a local static asset during implementation. Its provenance is recorded in the
commit message or adjacent source note. No proprietary material or credentials are added.

## 8. Stream Recovery and Error Handling

- The client tracks the last accepted event ID and rejects duplicates.
- Reconnection restores messages, active run state, pending approvals, and persisted activity
  before continuing live updates.
- A temporary disconnect shows Reconnecting without changing the run to Failed.
- Tool output truncation is explicit and preserves access to retained evidence.
- A tool failure remains attached to its step and does not become a detached error banner.
- Stale file saves keep the existing hash-conflict behavior.
- Missing Git metadata disables Git-specific detail but not the workspace.
- Unsupported preview types show metadata and download access rather than a blank pane.
- Unsupported physics continues to be refused by the simulator-neutral product layer.
- Simulator syntax remains inside adapter packages.

## 9. Testing Strategy

Every behavior change begins with a failing test, followed by the smallest implementation that
makes it pass. The complete suite runs before commit.

### 9.1 Unit tests

- Event deduplication and pairing.
- Phase derivation and terminal-state summaries.
- Subagent grouping.
- Interrupted reasoning handling.
- Permission presentation and run-level grant expiry.
- Markdown parsing and escaping.
- Pane constraint calculations and preference validation.
- Baseline and run change comparison.

### 9.2 API and integration tests

- Persisted events and live events produce the same presentation state.
- SSE reconnection resumes without duplicate steps.
- Run-scoped changes exclude pre-existing modifications.
- Terminal-created files and edits appear in the manifest.
- Git and non-Git workspaces both return honest change information.
- File and diff reads reject workspace escapes.
- Completed, failed, blocked, paused, cancelled, and recovered runs retain correct evidence.

### 9.3 Browser acceptance tests

The interface is exercised at wide desktop, constrained desktop, tablet, and narrow widths.
Acceptance checks verify:

- Shared pane borders remain pixel-aligned after resizing.
- The center workspace never falls below its minimum in three-pane mode.
- Breakpoint transitions use drawers without hidden controls.
- Width preferences restore and invalid values are clamped.
- Markdown renders correctly and safely.
- Activity rows group related events.
- Approvals remain actionable while reconnecting.
- File, diff, and validation links open the correct center view.
- The completion report opens at its beginning.

### 9.4 End-to-end TCAD scenario

The existing realistic research test workspace is used for a complete run:

1. Open the repository.
2. Start a conversation with a scientific repair task.
3. Observe repository inspection and operational reasoning.
4. Resolve a permission request.
5. Observe tool and subagent activity.
6. Inspect a live file change and run-scoped diff.
7. Execute focused validation.
8. Review final validation evidence and the completion report.

The scenario must prove that files are changed locally and that the final report corresponds to
the final workspace state.

## 10. Non-Goals

This work does not add:

- A collaborative multi-user editor.
- A full terminal emulator with interactive TTY support.
- A replacement code editor engine.
- Automatic Git staging, commits, pushes, or resets.
- New simulator physics or device-specific behavior.
- A new model gateway or multi-model router.
- A separate desktop-native application.

## 11. Delivery Boundaries

Implementation is complete when the approved layout, agent views, event presentation pipeline,
run-scoped change manifest, error recovery, local branding asset, and stated tests are present
and passing. Existing repository editing, approval, OpenHands runtime, DEVSIM workflow, and
future Sentaurus adapter boundary must continue to work without regression.
