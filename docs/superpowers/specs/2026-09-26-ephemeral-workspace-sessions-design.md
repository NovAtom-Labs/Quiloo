# Ephemeral Workspace Sessions

## Status

Approved product direction. This document defines the replacement for persistent repository conversations in the Agent Kronig desktop application.

## Objective

Agent Kronig must retain enough state to operate coherently while the desktop application is open, but it must not remember repository chats across application sessions.

Opening a repository starts a clean temporary agent session. Closing Agent Kronig, restarting its backend, or opening a different repository ends that session. Repository files and generated scientific artifacts remain unchanged. Chat messages, approvals, run events, agent runtime state, and technical activity do not survive the application session.

## User Experience

### Opening a repository

Opening a folder creates one temporary workspace session automatically. The user enters a task directly in the Chat pane without first creating or selecting a conversation.

The workspace URL contains only the workspace identifier. Conversation identifiers are not exposed in routes or UI state.

### Chat pane

The Chat pane contains:

- the messages exchanged during the current temporary session;
- the current narrative research trail;
- current approvals and run controls;
- links to current-session technical activity and changes.

The Chat pane does not contain:

- a conversation selector;
- a New conversation button;
- a conversation title;
- a conversation creation dialog;
- historical repository chats;
- controls for restoring previous sessions.

### Session boundary

The current temporary session ends when any of the following occurs:

- Agent Kronig closes;
- the backend restarts or crashes;
- the user opens a different repository;
- the current repository is explicitly closed.

Ending a session cancels nonterminal runs and denies unresolved approvals. Reopening the same repository starts with an empty Chat pane and does not resume, redirect to, or block on the previous session.

## Persistence Policy

### Persistent data

Only the following application data remains persistent:

- desktop settings;
- protected model credentials;
- update configuration;
- repository files created or edited through the workspace;
- simulator outputs, validation reports, and provenance artifacts written into the repository.

### Ephemeral data

The following data is scoped to one desktop process and must be deleted when that process ends or when stale session storage is found during the next startup:

- workspace session metadata;
- user and assistant messages;
- run records;
- approval requests and run-scoped permission grants;
- event streams and technical activity;
- change baselines and run change manifests;
- OpenHands conversation state and logs;
- transient file previews and session caches.

The implementation may use a temporary SQLite database and temporary OpenHands storage for reliability while the app is running. This storage is an implementation detail, is never presented as memory, and is deleted at the session boundary.

## Backend Architecture

### Persistent desktop root

The existing desktop data directory continues to hold settings, secrets, updater state, and a lifecycle lock. It must not be used as the runtime root for repository sessions.

### Temporary runtime root

At startup, the desktop backend creates a uniquely named temporary runtime directory beneath a dedicated session area. The repository IDE store, event feed, approval data, change tracking data, and OpenHands runtime use this directory.

The desktop data-directory lock is acquired before stale session cleanup. This prevents one Agent Kronig process from deleting another process's active session.

Startup performs these steps in order:

1. acquire the desktop data-directory lock;
2. remove stale temporary session directories left by an interrupted process;
3. run the one-time legacy repository-memory cleanup;
4. create a fresh temporary runtime root;
5. construct workspace and agent services against that runtime root;
6. start the loopback desktop server.

Graceful shutdown cancels active runs, denies pending approvals, closes database handles, and removes the temporary runtime root. A crash may leave the root behind, but the next startup removes it before creating a new session.

### Workspace session service

The public backend API exposes a workspace session rather than repository conversations.

Opening a workspace creates its temporary session automatically. Reopening the same workspace during the same process returns the current session. When no live run exists, opening a different workspace ends the previous session before creating the next one. There is at most one workspace session in the desktop process.

The agent runtime may continue to use an internal UUID as its execution and event correlation key. That key is not durable product memory and is not exposed as a user-managed conversation.

### API surface

Workspace-scoped routes replace conversation-management routes in the frontend contract. The required capabilities are:

- get the current workspace session;
- list and create current-session messages;
- start and control the current run;
- stream current-session events;
- list and resolve current approvals;
- inspect current-run changes and technical evidence.

Conversation creation, conversation listing, conversation selection, and conversation restoration routes are removed from the product API. Internal adapters may temporarily translate workspace-session calls to existing execution primitives during migration, but no persistent conversation behavior may remain.

### Concurrency

The single-writer rule remains. It applies only to a live run owned by the current process. No database record from an earlier process can lock a workspace.

Opening another repository while a run is executing must require the user to stop or finish the run. A repository switch must never silently abandon a live writer.

## Frontend Architecture

The frontend route is `/workspaces/{workspace_id}`. Restoring this route loads the repository and creates or retrieves the current process's temporary workspace session.

The frontend keeps one internal session identifier for API correlation, but it does not render or route by that identifier.

The agent panel header shows only session state and run controls. The space previously occupied by the conversation selector and conversation-management buttons is removed. Refresh remains available only if it refreshes current workspace files and current-session state.

When the repository changes, the frontend clears messages, activity, approvals, selected runs, submission recovery state, and event-stream connections before binding to the new temporary session.

When Agent Kronig restarts, the initial Chat pane always displays an empty-session prompt such as `Describe the task for this repository.`

## Legacy Data Cleanup

The first startup containing this change removes repository-memory data created by earlier versions:

- the persistent IDE SQLite database and its WAL or shared-memory files;
- persistent OpenHands conversation directories;
- legacy session caches whose paths are explicitly allowlisted as conversation state.

Cleanup runs only inside the Agent Kronig application data directory after the data-directory lock is held. It must use explicit allowlisted paths and must never traverse into a user repository.

A migration marker records completion so later startups do not repeat the legacy scan. Failure to remove a legacy path must not expose or restore that data. Startup reports a sanitized cleanup error and leaves the product in a clean-session state.

## Failure Handling

- If temporary runtime creation fails, Agent Kronig does not open a partially functional workspace.
- If stale-session cleanup fails, startup stops with a sanitized local error instead of loading stale memory.
- If graceful deletion fails after shutdown, the next startup retries cleanup.
- If the app crashes during a run, the next startup discards the entire stale runtime rather than reconstructing run state.
- If a repository switch is requested during active work, the switch is rejected until the current run reaches a terminal state.

## Security and Privacy

Temporary session paths use restrictive local permissions where supported. Credentials remain in the existing protected credential store and are never copied into the session database, event payloads, or OpenHands logs.

The legacy cleanup contains no repository paths derived from conversation content. Every deletion target is a fixed child of the locked Agent Kronig data directory.

## Compatibility

The behavior must be identical on Linux, macOS, and Windows. Temporary-path creation, cleanup, locking, and deletion use platform-neutral Python and Electron APIs. The design must not depend on a browser, shell profile, systemd, launchd, or Windows services.

Development launches use the same ephemeral-session behavior as packaged applications. Developers can inspect a live session while the app is running, but restarting development mode starts clean.

## Testing

Automated coverage must prove:

- opening a repository automatically creates one temporary session;
- the frontend contains no conversation selector, creation button, dialog, title, or conversation route;
- messages and activity remain available during the current process;
- reopening the same repository after backend restart yields an empty session;
- no earlier run or approval can block a new session;
- opening another repository clears the previous session after confirming no live run exists;
- an active run blocks repository switching;
- graceful shutdown removes temporary runtime storage;
- startup removes stale runtime storage left by a simulated crash;
- legacy persistent conversation storage is removed only from allowlisted application-data paths;
- repository files and generated artifacts survive session cleanup;
- settings and protected credentials survive session cleanup;
- the complete Python and desktop test suites remain green.

## Out of Scope

This change does not add repository memory, semantic retrieval, transcript search, cross-session summaries, pinned runs, cloud synchronization, or user-configurable retention. Those capabilities require a future design with explicit storage limits and researcher-facing controls.
