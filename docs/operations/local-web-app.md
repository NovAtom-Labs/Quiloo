# Local Repository Agent

## Start it

1. Install the project and DEVSIM as described in the README.
2. Copy `.env.example` to `.env`.
3. Put a valid Bedrock credential in `.env`. Do not paste it into source, a prompt, a report, or Git.
4. Start the Linux-local application:

```bash
.venv/bin/tcad-agent serve
```

5. On a headless Linux machine, use `.venv/bin/tcad-agent serve --no-browser` and open the printed loopback URL from the same machine.
6. The browser normally opens `http://127.0.0.1:8765`.

The launcher binds only to `127.0.0.1`. If a healthy instance is already running, it reuses it instead of starting a second server.

The compatibility entrypoint is:

```bash
.venv/bin/tcad-agent-web
```

The launcher binds only to `127.0.0.1`. If a healthy matching instance is already running, it reuses it. If an older instance owns the default port, the current build selects the next available loopback port.

## Repository agent workflow

1. Select `Open folder` and choose a repository with the native desktop picker. On headless Linux, enter an absolute path and select `Open path`.
2. Create a conversation and send a concrete repository task.
3. Watch the safe operational timeline plus normalized file, terminal, TCAD, validation, and subagent events in the Activity panel. The timeline can show sanitized task titles and a content-free model-generation state, but never raw provider reasoning or private task notes.
4. Decide any action that crosses the selected repository boundary or changes the wider machine. The approval card first explains the request in plain language. Expand Technical details to inspect the tool, permission category, risk, canonical path, or clipped command.
5. Select Approve for the current action, Approve all like this for matching permission categories during the current run, or Deny. Run-scoped grants expire when that run finishes and never carry into a new run.
6. Use Pause, Resume, or Stop as needed. Refreshing the page restores the persisted run, its category grants, and pending decisions.
7. Inspect the repository diff and the agent's final evidence before accepting the change.

Repository-local reads, edits, tests, builds, and validation commands run without interruption. The following actions require an explicit decision:

- access outside the selected repository, including `..` traversal and external absolute paths
- package installation or network commands
- destructive commands
- Git staging, commits, pushes, and other repository-history mutation
- remote or otherwise unknown actions

Subagents inherit the same workspace. High-risk child actions are denied and cannot widen the parent agent's access. When such an action is genuinely required, the primary agent must request it directly so the browser can present an approval card.

### Tools and subagents

The production OpenHands conversation receives file editing, terminal, task-tracking, native task delegation, and the typed `tcad_domain` tool. The TCAD tool validates portable specifications, compiles supported backends, searches an authorized local knowledge index, validates canonical results, and builds reports without accepting arbitrary simulator commands.

Available delegated agents include `code-explorer`, `bash-runner`, `general-purpose`, `tcad-researcher`, and `tcad-reviewer`. The web-research subagent is disabled because external network access has a separate trust and credential boundary.

### Acceptance prompt

Create a disposable test repository:

```bash
.venv/bin/python scripts/create_repl_test_repo.py
```

Open `test-workspaces/pn-junction-research` and send:

```text
Inspect this repository and RESEARCH_TASK.md. Diagnose and fix the scientific validation failures without changing researcher-owned inputs, run the repository checks, delegate a read-only scientific review, and report exact evidence.
```

Expected evidence includes three repaired source files, five passing visible tests, a read-only TCAD review result, unchanged `experiment.toml`, `data/`, and `tests/`, and a score of 100 from:

```bash
.venv/bin/python evaluations/repl/grade_workspace.py \
  --workspace test-workspaces/pn-junction-research
```

## TCAD work in a repository conversation

1. Open the repository that owns the specification, data, or requested evidence.
2. Create an Agent conversation and describe the research task, backend, geometry, materials, contacts, study, models, and required outputs.
3. Ask the agent to inspect or create a portable `ExperimentSpec` and check the selected backend capability.
4. Review the exact unsupported fields and any proposed approximation before authorizing execution.
5. Let the agent run the deterministic adapter, bounded runner, canonical normalizer, validators, and report builder through the typed `tcad_domain` tool.
6. Inspect changed repository files, activity evidence, validation results, and the final response.

The interface shows concrete actions and stage progress, not hidden model reasoning. Activity derives
its operational timeline from persisted run lifecycle, sanitized task plans, tools, delegation,
validation, and approval events. Model-generation lifecycle events contain no generated text. The separate
simulation workstation is no longer part of the browser product. Legacy `/simulate` links redirect
to the repository IDE, while the simulator APIs and CLI remain available.

## Backend behavior

DEVSIM runs locally now. The repository agent may inspect and edit DEVSIM-oriented project files, but actual simulation execution must still pass through the portable `ExperimentSpec`, capability check, approved plan, deterministic adapter, runner, normalizer, and validator. Use `examples/al-pn-al-equilibrium-devsim.yaml` for the explicit local approximation of the Al / p-Si / n-Si / Al request.

Sentaurus command generation and result contracts are implemented, but execution must stop as unconfigured until a licensed Linux runner is connected. Simulator-specific syntax remains behind the Sentaurus adapter. The repository agent does not receive a license bypass or an unrestricted remote shell. The full request is `examples/al-pn-al-equilibrium.yaml`.

Unsupported physics or observables must be visible. Do not silently remove them. If a researcher accepts an approximation, it must produce a new exact plan and a new approval.

## Local data

`TCAD_WORKSPACE` controls the SQLite request database, OpenHands persistence, event ledgers, compiled jobs, and bundles. The default is `.tcad-agent` in the repository. Agent conversations, messages, run states, approvals, and normalized events survive browser refresh and service reconstruction. A run interrupted by process restart returns as paused. Artifacts are local unless a configured licensed runner receives a signed Sentaurus job.

Stop the service before backing up `TCAD_WORKSPACE` so the SQLite database and write-ahead log remain consistent.

## Current limits

- Commands run as the current OS user. The pilot does not yet provide container or VM isolation.
- Approve applies to one action. Approve all like this applies to one permission category for the current run only. There is no cross-run allow-always rule.
- The pilot uses one configured Bedrock model for primary and delegated reasoning. Multi-model routing is planned later.
- Browser-based web research is disabled.
- Eligible UTF-8 text files can be edited in the workspace, but the pilot does not yet provide a rich language server or embedded Git diff editor. Binary, oversized, sensitive, and symlinked files remain read-only or refused.
- DEVSIM supports the reviewed one-dimensional silicon subset. Sentaurus execution remains unavailable until the licensed host passes conformance testing.

## Troubleshooting

- `model_configuration_error`: check the local Bedrock credential, region, and model ID. The response intentionally hides provider details and secrets.
- run remains paused after restart: select Resume. If a risky action was pending, review the restored approval card first.
- repeated approval for a harmless internal tool: update to the current build and restart the service. Task tracking, internal planning, completion, and typed TCAD operations are classified as local actions.
- native folder picker unavailable: install `zenity` or `kdialog` on desktop Linux, or enter an absolute repository path.
- terminal warning about `tmux`: install `tmux` for the most stable long-running agent terminal. The subprocess fallback remains supported for development.
- `backend_unsupported`: review the exact unsupported fields and select only an explicit approved approximation.
- `backend_unconfigured`: Sentaurus compilation may be available, but licensed execution is not connected.
- DEVSIM executable missing: set `TCAD_DEVSIM_PYTHON` to the installed DEVSIM environment.
- failed validation: inspect the validation report and preserve the bundle. The system does not relabel a converged but unphysical result as successful.
