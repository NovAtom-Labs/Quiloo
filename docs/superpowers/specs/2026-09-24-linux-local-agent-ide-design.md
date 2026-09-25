# Linux-Local Agent IDE Design

> Status: Superseded by the native desktop distribution. This document records the original
> browser-based prototype and is retained only as design history. It is not an installation or
> operation guide.

## 1. Objective

Agent Kronig will become a Linux-first repository-operating TCAD agent. A researcher selects a
repository, gives the agent a task in natural language, and watches the agent inspect files,
edit the repository, run commands, execute simulations, diagnose failures, and validate the
result through an iterative OpenHands conversation.

The browser remains the user interface. The agent runtime, repository access, simulator,
knowledge index, and credentials remain on the researcher's Linux machine. This provides the
interaction model of Cursor or Claude Code without requiring a native desktop application.

The existing simulator-neutral TCAD architecture remains authoritative. OpenHands may reason
about and modify repository content, but supported simulations continue through
`ExperimentSpec`, capability checks, deterministic adapters, bounded runners, canonical
results, and deterministic validation.

## 2. Success Criteria

The first complete version must let a researcher:

1. Start Agent Kronig on a supported Linux machine and open it in a browser.
2. Select an existing Git or non-Git repository as a workspace.
3. Start, pause, resume, and reopen an agent conversation for that workspace.
4. Ask the agent to inspect, create, edit, search, and validate repository files.
5. Watch tool calls, file changes, terminal output, simulation progress, and validation events
   as they occur.
6. Review all repository changes as a diff and restore an earlier checkpoint.
7. Allow routine operations inside the repository without repeated approvals.
8. Approve or deny precisely scoped access outside the repository.
9. Run the current DEVSIM workflow and later switch the same workflow to Sentaurus through
   the backend boundary.
10. Receive a final answer grounded in command output, simulator evidence, validation results,
    and the final workspace state.

## 3. Deployment Model

Agent Kronig is a local service with a browser-based IDE shell.

```text
Browser at localhost
        |
        v
Agent Kronig local service
        |
        +-- Workspace manager
        +-- Permission broker
        +-- OpenHands conversation runtime
        +-- File, terminal, search, and Git tools
        +-- TCAD domain tools and knowledge retrieval
        +-- Simulation orchestrator
        +-- Session and event stores
                  |
                  +-- DEVSIM adapter and local runner
                  +-- Sentaurus adapter and local or remote runner
```

The initial distribution uses Python, FastAPI, and the existing frontend stack. It exposes only
the loopback interface by default. The `tcad-agent serve` command starts the service and
opens the browser. The implementation must use POSIX behavior and must not depend on macOS
launchers, AppleScript, or platform-specific file APIs.

Docker or Podman isolation may be added as a runtime option. It is not required for the first
vertical slice because many licensed Sentaurus installations require controlled host
integration. The permission system must work whether commands execute on the host or in a
container.

## 4. Architectural Boundaries

### 4.1 Workspace layer

The workspace layer owns repository selection and filesystem scope. It resolves the selected
path to a canonical absolute path, records whether it is a Git repository, reads repository
instructions, and gives the agent a workspace-scoped view.

Every conversation belongs to exactly one workspace. Multiple conversations may use the same
workspace, but only one write-capable agent run may operate on that workspace at a time. Other
sessions may remain open in read-only mode until the writer finishes or pauses.

### 4.2 Agent layer

The agent layer uses the OpenHands SDK conversation runtime. It receives:

- A local workspace implementation
- File inspection and editing tools
- Repository search tools
- A bounded terminal tool
- Read-only Git inspection and diff tools
- Explicit Git mutation tools governed by policy
- The existing `tcad_domain` tool
- Curated TCAD skills and retrieved knowledge
- A system policy describing permissions, evidence, and completion rules

The agent examines every tool observation before choosing its next action. A task ends only
when its completion checks pass, the user stops it, a configured budget is exhausted, or the
agent reaches a blocked state that requires user input.

### 4.3 TCAD layer

The current TCAD pipeline remains a separate trusted subsystem:

```text
research intent
  -> ExperimentSpec
  -> schema and semantic validation
  -> backend capability decision
  -> deterministic adapter
  -> bounded runner
  -> CanonicalResult
  -> deterministic validation
  -> evidence bundle
```

For supported studies, agent-generated simulator syntax is not the production execution path.
The agent creates or updates the simulator-neutral experiment definition and invokes the typed
TCAD tools. Simulator-specific syntax stays in the adapter packages.

An advanced direct-file mode may let a researcher ask the agent to inspect or edit native
simulator files. Results from this mode must be labelled as direct and unvalidated unless they
are imported, normalized, and checked by the trusted pipeline.

### 4.4 Model layer

The model gateway remains replaceable. The pilot may use one Bedrock-hosted model for planning,
tool selection, diagnosis, and explanation. Conversation and tool interfaces must not depend on
one model's private response format so multi-model routing can be added later.

## 5. Core Components

### 5.1 `WorkspaceManager`

Responsibilities:

- Open and validate repository paths
- Create stable workspace identifiers
- Resolve and validate canonical paths
- Detect Git metadata, branch, and dirty state
- Read repository instructions such as `AGENTS.md`
- Coordinate one writer per workspace
- Provide repository metadata to the frontend and agent

It must not execute commands or decide permissions.

### 5.2 `PermissionBroker`

Responsibilities:

- Decide whether an operation is already allowed
- Produce approval requests for external or risky operations
- Record one-time and session grants
- Suspend and resume the requesting agent action
- Audit approvals, denials, expiry, and use

Permission classes are:

- Filesystem read
- Filesystem write
- Process execution
- External network access
- Package installation
- Credential use
- Destructive operation
- Git commit
- Git push or other remote mutation

Repository reads, repository writes, bounded local commands, and read-only Git inspection are
allowed by the normal workspace policy. The following actions require approval:

- Access outside the repository
- Destructive actions with material recovery cost
- Network access not already required by an approved configured service
- System or environment package installation
- Reading or injecting a credential not already configured for a named integration
- Creating a Git commit
- Pushing or otherwise mutating a remote service

### 5.3 `OpenHandsRuntime`

Responsibilities:

- Construct the OpenHands agent and conversation
- Load skills and repository context
- Attach workspace and domain tools
- Enforce iteration, time, token, and cost budgets
- Persist conversation state
- Resume suspended conversations
- Emit normalized lifecycle events

The runtime must not contain simulator-specific compilation logic.

### 5.4 `ToolBroker`

Responsibilities:

- Register file, search, terminal, Git, knowledge, and TCAD tools
- Route each call through permission checks
- Normalize tool output for persistence and streaming
- Apply timeout and output-size limits
- Record affected paths and process exit status
- Reject path escapes and unapproved external effects

Tools remain small and typed. Broad behavior belongs in the agent loop, not inside a single
opaque tool.

### 5.5 `ConversationStore`

The conversation store persists:

- Workspaces
- Conversations and user messages
- Agent runs
- Tool calls and observations
- Approval requests and decisions
- File checkpoints
- Usage and budget counters
- Final outcomes

SQLite is sufficient for the local pilot. Large logs and file snapshots live in a managed
runtime directory and are referenced by content hash.

### 5.6 `AgentEventStream`

The event stream converts internal activity into stable frontend events. The first version uses
Server-Sent Events for one-way streaming and ordinary HTTP endpoints for user commands and
approval decisions. A WebSocket is unnecessary until the product needs bidirectional terminal
input or collaborative sessions.

Event types include:

- Conversation status changed
- Assistant message delta
- Tool call started and completed
- Terminal output appended
- File changed
- Diff updated
- Approval requested and resolved
- Simulation stage changed
- Validation completed
- Run completed, stopped, failed, or blocked

Internal model reasoning is not exposed. The interface shows concise agent status and concrete
actions instead.

### 5.7 `SimulationOrchestrator`

The existing control, adapter, runner, result, validation, reporting, and evidence components
remain responsible for simulator work. The orchestrator exposes task-friendly typed operations
to OpenHands and emits progress events through the shared event stream.

### 5.8 `IDEFrontend`

The browser interface contains:

- Header: workspace, Git branch, simulator backend, model, and runtime state
- Left panel: files, repository search, conversations, and simulation runs
- Center panel: file viewer, editor, diff, terminal output, and results tabs
- Right panel: agent conversation, activity, questions, and approvals
- Bottom panel: diagnostics, tests, validation, and logs

The layout adapts to narrower screens but is optimized for a desktop Linux browser. The current
guided request, clarification, review, run, and results pages remain available as a focused TCAD
workflow. They become views within the larger workspace instead of the primary navigation model.

### 5.9 Delegated subagents

The primary OpenHands agent may delegate bounded work through the SDK task tool. Agent Kronig registers
the SDK's code-explorer, command-runner, and general-purpose agent definitions, plus reviewed
project agent definitions stored under `.agents/agents`. Delegated work inherits the parent
workspace, model, persistence directory, budgets, and confirmation policy.

Subagents are not a permission bypass. Their tool actions pass through the same confirmation and
event pipeline as parent actions, and their activity is attributed to the subagent task in the
browser. Parallel read-only investigation is allowed. Concurrent write-capable delegation is
limited to avoid conflicting edits in one repository, and the primary agent remains responsible
for reviewing delegated output and validating the final workspace state.

## 6. Agent Execution Lifecycle

### 6.1 Starting a task

1. The user opens a workspace and sends a prompt.
2. The service creates or resumes an OpenHands conversation.
3. The agent receives repository metadata, repository instructions, available skills, tool
   descriptions, current Git state, permission policy, and task budgets.
4. The run enters the `running` state and emits events to the browser.

### 6.2 Iterative work

The agent repeats this loop:

1. Inspect relevant repository state.
2. Search files and curated knowledge.
3. Choose one or more tool actions.
4. Request approval if an action crosses a policy boundary.
5. Execute allowed actions.
6. Inspect outputs, file changes, errors, and validation results.
7. Revise its approach and continue.

Routine repository operations do not interrupt the user. An approval request suspends only the
dependent action. Denial becomes a normal tool observation so the agent can find another safe
approach.

### 6.3 Completion

Before reporting success, the agent must evaluate task-specific evidence. For code changes this
normally includes relevant tests, formatters, static checks, and the final diff. For TCAD work it
also includes schema validation, backend capability checks, simulator completion, canonical
result validation, and requested-output completeness.

The final response contains:

- What changed
- Which files changed
- Commands and simulations run
- Validation evidence
- Approvals used
- Known limitations or unverified items
- Suggested next action when appropriate

### 6.4 Pause, resume, stop, and recovery

A user may pause or stop an active run. Browser closure does not erase the conversation. By
default, an active local run continues when the browser disconnects unless the user selected
pause-on-disconnect.

After a process or service restart, conversations that were waiting for approval remain waiting.
Runs interrupted during a tool call become paused and require an explicit resume. The system
never assumes that an interrupted write or external mutation completed successfully.

## 7. Filesystem and External Access

### 7.1 Default workspace grant

Opening a repository grants the agent read and write access within that repository for the
conversation. The grant applies to canonical paths below the repository root. It does not apply
to paths reached through a symlink that resolves outside the root.

### 7.2 External access request

If the prompt names an external path, or the agent discovers it needs one, the broker creates an
approval request before access. The request displays:

- Exact canonical target
- Requested operation
- Reason
- Proposed command or tool
- Potential side effects
- Requested duration

The user may allow the action once, allow the same scope for the current session, or deny it.
Persistent cross-session filesystem grants are excluded from the first version to avoid hidden
long-lived trust.

### 7.3 Grant semantics

- A read grant never implies write access.
- A child-path grant never implies parent access.
- A directory grant covers only the approved operation within that directory.
- Globs are expanded and displayed as concrete targets before approval.
- Paths are canonicalized again at execution time to prevent time-of-check path substitution.
- An external command and its external file access are independently authorized when necessary.
- Grants expire when the conversation closes or the user revokes them.

### 7.4 Credentials

Secrets are stored outside conversation text and normal tool output. Approved integrations inject
secrets directly into the relevant process or API client. The model sees a secret identifier and
availability status, not the secret value. Attempts to read common credential files require a
high-risk approval and may be refused by organization policy.

## 8. Terminal and Process Execution

The terminal tool executes argument arrays without an implicit shell where practical. Commands
that require shell syntax run through an explicit shell tool whose full source text is visible in
the activity stream.

Each process has:

- A canonical working directory
- A sanitized inherited environment
- An explicit secret injection set
- A timeout
- Output byte limits
- A process-group identifier for cancellation
- Captured stdout, stderr, and exit status

The broker inspects the working directory and declared path arguments before execution. Runtime
isolation supplies the actual enforcement boundary. Initial Linux support may use OS user
permissions and tool-level path checks, with optional Docker or Podman containment. A later
enterprise profile may use a dedicated worker user, namespaces, seccomp, and network policy.

## 9. File Changes, Diff, and Checkpoints

Agent file writes are atomic. Before the first write in a run, Agent Kronig records the baseline content
hash of affected files. After each write it emits a file-changed event and updates the visible
diff.

Checkpoints store content-addressed patches and metadata rather than creating automatic Git
commits. A researcher can restore one file or the complete checkpoint. Restoration itself is a
visible workspace mutation and never discards unrelated changes silently.

Agent Kronig distinguishes pre-existing user changes from agent changes. It must not overwrite,
revert, stage, or commit unrelated user work. If an intended edit conflicts with a file that
changed after the agent read it, the write fails with a stale-content observation and the agent
must reread and reconcile the file.

## 10. Git Behavior

Read-only operations such as status, diff, log, branch inspection, and blame are available inside
the workspace. Mutating Git operations are separated:

- Staging requires an explicit user action or a task-specific approval.
- Committing requires approval that shows the included paths and proposed message.
- Pushing requires a separate approval that shows the remote, branch, and commits.
- Destructive history changes are refused by default and require an organization policy change,
  not a conversational approval.

The agent may propose a commit without performing it.

## 11. Error Handling

All tool failures become structured observations with a stable code, human-readable message,
captured evidence, and retry classification.

Failure classes are:

- Correctable input error
- Permission denied
- User denial
- Command failure
- Timeout or cancellation
- Capability unsupported
- Simulator convergence failure
- Validation failure
- Infrastructure unavailable
- Model response invalid
- Budget exhausted

The agent may retry only when it changes a relevant input, configuration, or strategy. Identical
retries count toward stuck detection. Repeated equivalent failures move the run to `blocked` and
state the exact evidence and required user decision.

Simulator failure never becomes a successful report. Unsupported physics is refused rather than
silently approximated. Partial results remain inspectable but are clearly labelled incomplete.

## 12. State Model

An agent run has one of these states:

```text
queued
running
waiting_for_approval
waiting_for_user
paused
completed
failed
blocked
cancelled
```

State transitions are persisted before being streamed. The browser derives its controls from the
persisted state, not from optimistic client assumptions.

Approval requests have separate `pending`, `approved`, `denied`, `expired`, and `consumed`
states. One-time approval can authorize exactly one matching operation.

## 13. API Surface

The first version adds endpoints in these groups:

- `/api/workspaces`: open, list, inspect, and close workspaces
- `/api/conversations`: create, list, read, and resume conversations
- `/api/runs`: start, pause, resume, stop, and inspect agent runs
- `/api/events`: stream normalized conversation events
- `/api/approvals`: inspect, approve, deny, and revoke grants
- `/api/files`: list, read, update, and restore workspace files
- `/api/diffs`: retrieve agent and workspace diffs
- `/api/terminal`: retrieve command records and output
- Existing request and result endpoints: continue serving the guided TCAD workflow

Every mutating request includes an expected resource version so stale browser actions fail safely.

## 14. Knowledge and Skills

Repository instructions, OpenHands skills, and retrieved TCAD knowledge have distinct roles:

- Repository instructions define local conventions and verification commands.
- Skills define reusable agent workflows and decision rules.
- Retrieval supplies reviewed technical facts with citations.
- Deterministic code defines schemas, capabilities, compilation, execution, and validation.

Retrieved content is evidence, not executable instruction. Untrusted repository content cannot
override the permission broker, secret policy, simulator boundary, or validation requirements.

The knowledge index remains versioned and records source, trust, review status, backend, version,
license, access class, and content hash. Proprietary Sentaurus material remains on an approved
licensed machine or restricted store.

## 15. Testing Strategy

### 15.1 Unit tests

Unit tests cover:

- Canonical path and symlink handling
- Permission matching, expiry, and single-use consumption
- Command policy and environment construction
- Workspace writer locking
- State transitions
- Event serialization and ordering
- Atomic file writes and stale-content detection
- Diff attribution and checkpoint restoration
- Error classification and retry limits

### 15.2 Integration tests

Integration tests run an OpenHands conversation against temporary Git repositories. Fixtures
exercise inspection, editing, command execution, failing tests, corrective edits, approvals,
denials, pause and resume, browser reconnection, and service restart recovery.

DEVSIM integration tests verify the complete path from conversation to experiment, execution,
canonical result, validation, evidence bundle, and results viewer. Licensed Sentaurus tests remain
opt-in and run only on a configured host.

### 15.3 Security tests

Security tests attempt:

- `..` path traversal
- Symlink escape
- Shell redirection outside the repository
- Environment and credential exfiltration
- Approval reuse after consumption
- Time-of-check path substitution
- Unauthorized network access
- Oversized output and process trees
- Prompt injection from repository and retrieved content

### 15.4 Browser tests

Browser tests verify workspace selection, conversation streaming, file navigation, editor writes,
diff updates, terminal output, approval cards, pause and resume, simulation progress, and results
interaction. The supported baseline is current Chromium and Firefox on Linux.

## 16. Delivery Sequence

The architecture should be delivered as vertical slices:

1. Workspace selection, persistent conversations, repository inspection, and event streaming.
2. File editing, repository search, bounded terminal execution, diffs, and checkpoints.
3. Permission broker and approved access outside the repository.
4. Iterative OpenHands loop with tests, recovery, budgets, and pause or resume.
5. TCAD domain-tool integration, DEVSIM execution, validation, and embedded results.
6. Linux packaging, operational hardening, and Sentaurus-host integration.

Each slice must leave the existing guided workflow operational. The implementation may replace
internal web components when necessary, but it must preserve the simulator-neutral domain
contracts and evidence format.

## 17. Explicit Non-Goals for the First Version

The first version does not include:

- Real-time collaboration between multiple researchers
- A cloud-hosted multi-tenant workspace service
- A native Electron or Tauri shell
- An unrestricted root shell
- Automatic Git commits or pushes
- Persistent external filesystem grants
- General remote desktop control
- Bypassing the deterministic TCAD adapter for supported production runs
- Calibrated process simulation or unsupported device physics

These constraints keep the first implementation focused on a reliable Linux-local agent IDE and
leave clear extension points for later deployment models.
