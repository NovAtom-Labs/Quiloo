# Quiloo

Quiloo is NovAtom Labs' simulator-neutral TCAD research agent. It turns a researcher's natural-language device study into a strict experiment specification, asks only for consequential missing inputs, presents the exact normalized plan for approval, runs an allowed simulator workflow, validates the numerical output, and packages reproducible evidence.

The pilot runs DEVSIM locally. The same researcher workflow and portable `ExperimentSpec` are designed to target a licensed Sentaurus installation through a restricted remote runner. Simulator-specific syntax, execution, and normalization stay behind adapters, so devices are described as data instead of hardcoded product modes.

> **Pilot status:** the local DEVSIM workflow is operational. Sentaurus compilation, signing, normalization, and conformance infrastructure are implemented, but licensed execution remains intentionally disabled until the licensed machine passes the integration checklist.

## Why Quiloo

General-purpose language models are useful for interpreting research intent and operating a repository, but they are not reliable authorities for TCAD syntax, physical support, units, or numerical validity. Quiloo separates those responsibilities:

- The model interprets the request, inspects repository evidence, edits files, runs bounded commands, and delegates review tasks.
- A strict schema owns units, geometry, doping, contacts, physics, studies, and observables.
- Backend manifests decide whether DEVSIM or Sentaurus can represent the request.
- Deterministic compilers generate simulator inputs.
- Bounded runners execute only approved jobs.
- Validators, not the model, decide whether produced evidence passes.
- A versioned knowledge layer supplies reviewed TCAD context with citations.

The repository agent receives OpenHands file, terminal, task-tracking, delegation, and typed TCAD tools. Deterministic schemas, capability manifests, adapters, runners, and validators remain the authority for simulator execution and scientific acceptance.

## Researcher workflow

```text
Natural-language research request
              |
              v
     Consequential questions
              |
              v
  Simulator-neutral ExperimentSpec
              |
              v
 Schema + semantic + capability checks
              |
              v
 Exact plan review and researcher approval
              |
              v
 Deterministic DEVSIM or Sentaurus adapter
              |
              v
       Bounded simulator runner
              |
              v
 Canonical result + physical validation
              |
              v
 Evidence bundle, report, hashes, and audit ledger
```

The local application now opens into a Linux-first repository IDE. A researcher can open a local
Git or non-Git repository, inspect its directory tree and Git state, create a persistent
conversation, and return to the same conversation URL after a browser or service restart.

### Repository agent workflow

1. Open a repository with the native folder picker or enter its absolute path.
2. Create a conversation and describe the intended repository task.
3. Quiloo reads and edits files, searches the repository, runs tests or validation commands, uses typed TCAD operations, and may delegate bounded work to a specialist subagent.
4. Live activity shows tool names, canonical paths, commands, outcomes, validation evidence, and delegated task results. Internal chain-of-thought is never shown or stored.
5. Repository-local reads, edits, tests, builds, and validation run without interruption. Access outside the selected repository, package installation, network activity, destructive commands, Git mutation, and remote mutation stop at an approval card.
6. The researcher can approve once, deny, pause, resume, stop, refresh, or return later. Conversations, messages, run state, approvals, and normalized events are persisted locally.

The selected repository is the default authority boundary. A parent agent and every delegated subagent use the same canonical workspace and policy. A subagent cannot widen access, and a high-risk child action is denied until the parent workflow obtains an allowed decision.

Available agent tools are:

- repository-scoped file inspection and editing
- bounded terminal execution from the repository root
- persistent task tracking
- the `tcad_domain` tool for specification validation, backend compilation, knowledge retrieval, result validation, and report generation
- native OpenHands task delegation

Built-in `code-explorer`, `bash-runner`, and `general-purpose` subagents are available. Quiloo also registers `tcad-researcher` for evidence-backed TCAD investigation and `tcad-reviewer` for read-only checks of units, capability support, requested outputs, and validation evidence. Network-enabled research is disabled by default.

Try this against the generated acceptance repository:

```text
Inspect this repository and RESEARCH_TASK.md. Diagnose and fix the scientific validation failures without changing researcher-owned inputs, run the repository checks, delegate a read-only scientific review, and report exact evidence.
```

The `Guided simulation` view retains the established TCAD workflow. In that view, the researcher:

1. Describes the intended device study and selects a backend.
2. Answers missing values that affect the physical structure or boundary conditions.
3. Reviews normalized geometry, doping, contacts, study parameters, equations, models, observables, backend, and declared limitations.
4. Approves the immutable plan digest.
5. Runs the simulation.
6. Explores spatial fields, operating points, device structure, and validation evidence in the interactive results workspace.
7. Downloads the evidence bundle when files are needed for audit or external analysis.

Repeated Run actions return the existing terminal state. They do not create duplicate simulator jobs.
Each stage has a persistent URL. Refreshing or revisiting a clarification, review, or results page restores the same request from the local request database.

## What works now

| Area | Current capability |
| --- | --- |
| Repository IDE | Three-panel local workspace with canonical repository paths, Git state, directory inspection, persistent conversations, activity streaming, and stable URLs |
| Guided research interface | Four sequential local pages for request, clarification, plan approval, and interactive results at `/simulate` |
| Portable specification | Strict one-dimensional `ExperimentSpec` with dimensional quantities and rejection of unknown fields |
| Structures | Composable ordered silicon regions, without named-device execution branches |
| Doping | Constant donor and acceptor profiles |
| Contacts | DEVSIM ohmic contacts; Sentaurus ohmic and explicit metal work-function mappings |
| Studies | Equilibrium and bounded DC sweeps |
| DEVSIM | Deterministic compilation, local subprocess isolation, normalization, validation, reports, and evidence bundles |
| Sentaurus | Deterministic `sdevice.cmd` compilation, source maps, hashes, signed remote protocol, strict result normalization, and conformance rules |
| Knowledge | Manifest-gated retrieval with source metadata, review state, backend/version filters, content hashes, and citations |
| Agent runtime | Persistent OpenHands execution with file editing, terminal commands, task tracking, typed TCAD tools, native delegated subagents, live activity, pause/resume/stop, and approval-gated external access |
| Recovery | Bounded, allowlisted recovery policy with explicit failure classification |
| Auditability | Persistent request states, immutable plan digests, event ledgers, artifact SHA-256 values, and atomic bundles |

### Exact backend capability

The manifests below are enforced before compilation. A model cannot expand these capabilities.

| Capability | DEVSIM pilot | Sentaurus adapter |
| --- | --- | --- |
| Execution | Configured locally | Unconfigured until the licensed host is connected |
| Dimension | 1D | 1D |
| Material | Silicon | Silicon |
| Maximum regions | 32 ordered contiguous regions | 32 ordered contiguous regions |
| Doping profiles | Constant donor or acceptor concentration | Constant donor or acceptor concentration |
| Contacts | Two endpoint ohmic contacts | Endpoint ohmic or metal work-function contacts |
| Studies | Equilibrium and DC sweep | Equilibrium and DC sweep |
| Maximum DC points | 10 | 10 |
| Equations | Poisson, electron continuity, hole continuity | Poisson, electron continuity, hole continuity |
| Statistics | Boltzmann | Boltzmann or Fermi |
| Mobility | Constant mobility | Constant mobility and reviewed Sentaurus mobility mapping |
| Recombination | SRH | SRH and Auger |
| Band-gap narrowing | No | Yes |
| Local execution budget | 120 seconds by default | Licensed runner policy will decide |

DEVSIM currently normalizes these outputs:

- terminal current density
- electrostatic potential
- electric field
- electron density
- hole density

The Sentaurus result contract additionally represents terminal charge, space-charge density, conduction and valence bands, Fermi level, electron and hole current densities, electron and hole mobility, and recombination rate. Those fields become executable only after the licensed runner and native-result extractor pass conformance testing.

### Interactive results workspace

Completed simulations open inside the application rather than forcing researchers to download files. The results page provides:

- simulator, version, run-state, field-count, and validation summary cards
- built-in-potential and equilibrium-current metrics when applicable
- field selection across every normalized spatial output
- linear and logarithmic scales, zoom, position control, reset, and point hover readout
- minimum, maximum, sample count, units, and simulated position range
- terminal current and bias-point tables
- the exact regions, extents, material, and doping that produced the result
- searchable numerical samples for the selected field
- every deterministic validation check and its status
- collapsible evidence downloads for audit and external analysis

## Deliberate pilot limits

Quiloo is currently intended for small exploratory drift-diffusion studies, architecture validation, and researcher workflow testing. It is not yet a fabrication-calibrated prediction system.

| Limitation | Current consequence |
| --- | --- |
| One spatial dimension | No lateral geometry, junction curvature, edge fields, trenches, fins, planar gates, or process topography |
| Silicon only | No SiC, GaN, Ge, III-V, oxide, metal, or heterojunction region simulation |
| Constant profiles only | No Gaussian, error-function, implanted, graded, tabulated, or process-derived doping |
| Two endpoint contacts | No transistor gate terminal, body contact, internal electrode, or multi-terminal device operation |
| Drift-diffusion only | No hydrodynamic, energy-balance, ballistic, quantum-correction, Monte Carlo, or density-gradient transport |
| Electrical and isothermal | No self-heating, optical generation, radiation, stress, mechanics, or circuit co-simulation |
| Small bounded sweeps | At most 10 DC points; no transient, AC, noise, breakdown search, continuation campaign, or multidimensional parameter sweep |
| No calibration loop | Results are not automatically fitted to process measurements, compact models, or fabrication data |
| Pilot clarification rules | Automatic pre-model questions currently recognize common silicon p/n thickness and aluminum contact ambiguity; less familiar omissions rely on the model and plan review |
| Model intent extraction | Researchers must verify that every requested model and observable appears in the normalized plan. An omitted request must not be approved |
| DEVSIM approximation | Metal work function, Fermi statistics, Auger, band-gap narrowing, band diagrams, mobility output, and recombination output are outside the reviewed local adapter |
| Sentaurus host absent | Command generation and result contracts exist, but real licensed execution remains disabled |
| Local-process isolation | Repository commands run as the current OS user; the pilot does not yet provide a container, VM, or per-researcher operating-system sandbox |
| Approval granularity | Approval is per high-risk action. There is no durable allow-always rule in the pilot |
| Single-model pilot | The primary agent and delegated agents use the configured Bedrock model. Multi-model routing remains a later optimization |

No arbitrary user or model-generated simulator syntax is executed. Adding a new material, model, profile, contact, study, or observable requires a schema change, capability declaration, deterministic adapter mapping, normalization, validation, and tests.

## Architecture

The stable product is the experiment and evidence workflow. DEVSIM and Sentaurus are replaceable execution backends.

| Layer | Responsibility |
| --- | --- |
| `domain` | Strict simulator-neutral scientific intent and units |
| `capabilities` | Backend support, resource limits, refusal reasons, and execution availability |
| `model_gateway` | Structured proposal boundary around the configured online model |
| `knowledge` | Authorized ingestion, retrieval, review metadata, and citations |
| `control` | Request lifecycle, clarification, immutable approval, orchestration, and duplicate-run protection |
| `adapters` | Deterministic backend compilation and native-result normalization |
| `runners` | Local bounded execution and signed licensed-host submission |
| `results` | Canonical simulator-neutral numerical results |
| `validation` | Numerical, physical, conservation, provenance, and completeness checks |
| `bundles` | Atomic evidence packaging, reports, manifests, and artifact hashes |
| `agent` | OpenHands runtime, repository policy, normalized events, typed TCAD tools, and bounded subagents |
| `ide` | Canonical local workspaces, persistent conversations, runs, approvals, messages, and ordered activity events |
| `web` | Browser IDE, guided TCAD workflow, local HTTP API, and Server-Sent Events |

Every backend implements the same conceptual boundary:

```python
manifest -> CapabilityManifest
compile(spec, workspace) -> CompiledJob
normalize(native_run) -> CanonicalResult
```

Adding a structure expressible through existing concepts requires a new example or evaluation case, not product code. Adding a genuinely new material, contact, profile, model, study, or observable requires an explicit schema decision, backend support declaration, deterministic mapping, normalization, validation, and tests.

See [Architecture](docs/architecture.md) for the complete contract description.

## Knowledge and TCAD skills

The knowledge layer is designed to close the TCAD knowledge gap without allowing retrieved text to control execution.

Sources enter through a manifest containing:

- source ID and title
- public URL or controlled local location
- license and access classification
- trust level and review state
- simulator backend and version
- content hash and citation metadata

Only allowlisted text formats are indexed. Retrieval results are filtered by backend and version, and every passage carries a citation. Retrieved material can help the model construct or explain a specification, but it cannot override schemas, capability manifests, approval, compiler templates, or validators.

The repository includes focused skills for specification, capability checking, DEVSIM compilation, solver recovery, result validation, source citation, reporting, and the Sentaurus boundary.

Public DEVSIM material can be indexed locally. Proprietary Sentaurus manuals and examples must remain on the licensed machine or in another approved restricted store and must never be committed here.

## Requirements

- Linux for the supported local IDE and runner workflow
- Python `3.13`
- a DEVSIM Python environment for real local simulations
- an Amazon Bedrock API key for the natural-language model gateway
- Sentaurus only on a separately configured and licensed host

## Installation

Clone the repository and create the project environment:

```bash
git clone https://github.com/NovAtom-Labs/Quiloo.git
cd Quiloo

/usr/local/bin/python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install . --no-deps
```

Install DEVSIM separately. Point Quiloo to its Python executable when it is not available at the default sibling location:

```bash
export TCAD_DEVSIM_PYTHON=/absolute/path/to/devsim/.venv/bin/python
```

The development machine used for the pilot currently uses DEVSIM `2.9.1`, pinned from upstream commit `43b41ca845184c47e22b72d144db7e7db8509377`.

## Configuration

Create the ignored local configuration:

```bash
cp .env.example .env
```

Supported settings:

| Variable | Purpose |
| --- | --- |
| `AWS_BEARER_TOKEN_BEDROCK` | Bedrock API key used by the online model gateway |
| `AWS_REGION_NAME` | Region in which the Bedrock key was generated and the request originates |
| `LLM_MODEL` | OpenHands/LiteLLM model identifier |
| `TCAD_REASONING_EFFORT` | Pilot reasoning-effort setting |
| `TCAD_DEVSIM_PYTHON` | DEVSIM-capable Python executable |
| `TCAD_WORKSPACE` | Local request database, job, and bundle root; defaults to `.tcad-agent` |
| `TCAD_SENTAURUS_ENDPOINT` | Approved licensed-runner HTTPS endpoint |
| `TCAD_SENTAURUS_VERSION` | Exact configured licensed release |

The pilot template currently selects the global Claude Sonnet 4.6 Bedrock inference profile in `ap-south-1`. A Bedrock API key must be generated in the same region. Keep credentials only in `.env` or a secret manager.

Never commit `.env`, API keys, signing keys, proprietary manuals, licensed examples, or generated local workspaces. Revoke and rotate any credential disclosed in a prompt, chat, log, report, or commit.

## Run the Linux-local application

Start the supported Linux entrypoint from the repository:

```bash
.venv/bin/tcad-agent serve
```

Use `--no-browser` on a headless Linux session and open the printed loopback address manually:

```bash
.venv/bin/tcad-agent serve --no-browser
```

The application binds only to `127.0.0.1`, normally at
[http://127.0.0.1:8765](http://127.0.0.1:8765). The launcher reuses an existing instance only when
its source and non-secret model configuration match the current checkout. If an older instance
owns that port, the updated application starts on the next available loopback port. The legacy
`tcad-agent-web` entrypoint remains available for compatibility.

### Open and resume a repository workspace

1. Select `Open folder` to use the native desktop picker. On headless Linux, enter an absolute repository path instead.
2. Select `Open path` to register the canonical path and inspect its top-level entries.
3. Select `New conversation`, provide a title, and send the first prompt.
4. Watch file, command, validation, and subagent events in the activity stream. Resolve an approval card only after checking its exact target and effect.
5. Pause, resume, or stop the active run when needed.
6. Bookmark or reload the resulting `/workspaces/<id>/conversations/<id>` URL to restore the workspace, conversation, messages, run state, approvals, and activity stream.
7. Select `Simulation` to open the validated TCAD workflow at `/simulate`.

Workspace metadata, conversations, messages, and IDE events are stored in
`.tcad-agent/ide.sqlite3` by default. Guided requests remain in
`.tcad-agent/requests.sqlite3`, and simulation bundles remain below the same runtime root. Change
the root with `TCAD_WORKSPACE`. Stop the local service before copying that directory for backup so
the SQLite database and write-ahead log remain consistent.

Create the reproducible repository-agent evaluation workspace with:

```bash
.venv/bin/python scripts/create_repl_test_repo.py
```

It is written to `test-workspaces/pn-junction-research`, which is ignored by Git. The committed acceptance test uses an isolated temporary copy and a deterministic OpenHands test model:

```bash
OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/e2e/test_agentic_repl.py -q
```

To run the same acceptance path against the configured Bedrock model, explicitly opt in:

```bash
OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest tests/e2e/test_agentic_repl.py \
  --run-live-bedrock -m live_bedrock -q
```

For the main pilot demonstration, paste [the Al / p-Si / n-Si / Al prompt](examples/prompts/al-pn-al-equilibrium.md), select DEVSIM, and answer the requested thickness and contact questions. The local run covers the DEVSIM-supported subset. Verify all omitted Sentaurus-only physics during plan review.

## CLI examples

Validate portable specifications:

```bash
.venv/bin/tcad-agent validate examples/pn-junction.yaml
.venv/bin/tcad-agent validate examples/pin-diode.yaml
.venv/bin/tcad-agent validate examples/multiregion-equilibrium.yaml
.venv/bin/tcad-agent validate examples/al-pn-al-equilibrium-devsim.yaml
.venv/bin/tcad-agent validate examples/al-pn-al-equilibrium.yaml
```

Run a DEVSIM study after explicit approval:

```bash
.venv/bin/tcad-agent run examples/pn-junction.yaml \
  --backend devsim \
  --approve \
  --output runs
```

Compile the full Sentaurus example without executing licensed software:

```bash
.venv/bin/tcad-agent compile examples/al-pn-al-equilibrium.yaml \
  --backend sentaurus \
  --output compiled/al-pn-al-sentaurus
```

Inspect an agent evaluation case:

```bash
.venv/bin/tcad-agent evaluation show metal-silicon-junction-equilibrium
```

Build and query the approved local knowledge index:

```bash
.venv/bin/tcad-agent knowledge build \
  --manifest knowledge-sources/manifests/sources.yaml \
  --root /absolute/path/to/approved/source/root

.venv/bin/tcad-agent knowledge search "ohmic contact equation" \
  --backend devsim \
  --version 2.9.1
```

## Example studies

Examples are ordinary specifications, not privileged device modes:

| File | Purpose |
| --- | --- |
| `examples/pn-junction.yaml` | Two-region silicon PN reference with a bounded DC sweep |
| `examples/pin-diode.yaml` | Three-region silicon PIN reference using the same generic path |
| `examples/multiregion-equilibrium.yaml` | Four-region p+ / p / n / n+ silicon equilibrium study |
| `examples/al-pn-al-equilibrium-devsim.yaml` | Explicit DEVSIM approximation of the pilot metal-contact equilibrium problem |
| `examples/al-pn-al-equilibrium.yaml` | Full Sentaurus-targeted form with work functions and advanced requested models |

Researchers can compose other supported one-dimensional silicon stacks by changing data. No named-device branch is required.

### Copy-paste web prompts

These prompts stay inside the enforced capability boundary:

| Prompt | Backend | What it demonstrates |
| --- | --- | --- |
| [Silicon PN forward-bias sweep](examples/prompts/pn-dc-sweep.md) | DEVSIM | Two regions, asymmetric doping, three DC points, carrier and potential fields |
| [Silicon PIN forward-bias sweep](examples/prompts/pin-dc-sweep.md) | DEVSIM | Three regions, near-intrinsic middle region, electric field and current |
| [Four-region equilibrium stack](examples/prompts/multiregion-equilibrium.md) | DEVSIM | Generic p+ / p / n / n+ composition without a named-device code path |
| [Al / p-Si / n-Si / Al equilibrium](examples/prompts/al-pn-al-equilibrium.md) | Sentaurus target, DEVSIM subset | Work-function contacts, advanced model intent, and explicit local limitations |

Useful prompt pattern:

~~~text
Using the DEVSIM backend, simulate a one-dimensional silicon structure at
300 K. List every region in left-to-right order with its extent, mesh spacing,
donor or acceptor species, and concentration. Use ohmic endpoint contacts.
Select equilibrium or define one driven contact with DC start, stop, and step.
Request only terminal current, potential, electric field, electron density,
and hole density. Use Boltzmann statistics, constant mobility, and SRH.
~~~

Prompts work best when they state explicit units, ordered region boundaries, contact locations and kinds, temperature, study bounds, models, and required outputs. Ambiguous prompts intentionally trigger clarification or refusal.

## Evidence and validation

A completed run produces an atomic bundle:

```text
<run-id>/
  experiment.json
  compiled/
  logs/stdout.log
  logs/stderr.log
  native/native_result.json
  results/canonical.json
  results/fields.csv
  results/field-plots.svg
  validation/report.json
  report.md
  manifest.json
  events.jsonl
```

Validation covers execution status, convergence, point counts, finite values, sweep ordering, terminal conservation, carrier bounds, requested-output completeness, and provenance. Equilibrium runs additionally require every terminal current to approach zero. Reviewed 300 K abrupt silicon p-n cases compare the simulated potential range with the analytical built-in potential. Other structures receive the generic checks and mark that narrow analytical check not applicable. Each check distinguishes configured, simulator-observed, derived, and statically verified evidence. Mandatory failure produces a failed bundle state. Reports and the interactive viewer read structured canonical results only; logs remain evidence and are not treated as a numeric source of truth.

## Sentaurus integration path

The repository already contains:

- deterministic Sentaurus Device command generation
- reviewed mappings for Fermi statistics, mobility, SRH, Auger, and band-gap narrowing
- metal work-function and ohmic contact rendering
- compiler, input, runtime, and experiment hashes
- source mapping from command lines to specification paths
- Ed25519-signed ZIP submission with version and expiry binding
- replay, traversal, size, file-count, output, executable, and argument controls
- strict native JSON normalization with SI conversion
- case-scoped DEVSIM-to-Sentaurus conformance rules

The licensed machine must still provide and review the exact Sentaurus release, executable identity, structure or mesh generation, native-to-JSON extraction, TLS identity, quotas, restricted knowledge location, and domain-expert golden cases. Until that checklist passes, execution stays `unconfigured` while local DEVSIM remains independently usable.

See [Sentaurus integration](docs/operations/sentaurus-integration.md) for the full licensed-host checklist and one-day connection procedure.

## Testing

Run the complete ordinary verification suite:

```bash
OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q
.venv/bin/ruff check src tests
.venv/bin/mypy --strict src
git diff --check
```

Two tests are expected to remain skipped on a normal development machine: the live Bedrock call and real licensed Sentaurus execution.

Run the Bedrock smoke test only with a valid local credential:

```bash
OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest \
  tests/e2e/test_pilot_acceptance.py \
  --run-live-bedrock -m live_bedrock -q
```

Run licensed cross-backend conformance only after the Sentaurus host is configured:

```bash
.venv/bin/pytest -m sentaurus \
  tests/integration/test_cross_backend_conformance.py -q
```

The detailed manual and automated acceptance procedure is in [Pilot acceptance](docs/testing/pilot-acceptance.md).

## Repository layout

```text
src/tcad_agent/domain/            portable experiment contract
src/tcad_agent/capabilities/      backend support and refusal
src/tcad_agent/model_gateway/     structured online-model boundary
src/tcad_agent/knowledge/         authorized ingestion and retrieval
src/tcad_agent/ide/               local workspaces, conversations, and activity events
src/tcad_agent/control/           request lifecycle and orchestration
src/tcad_agent/adapters/          deterministic simulator translations
src/tcad_agent/runners/           bounded local and remote execution
src/tcad_agent/results/           canonical simulator-neutral results
src/tcad_agent/validation/        numerical and physical checks
src/tcad_agent/bundles/           immutable evidence packaging
src/tcad_agent/web/               local researcher application
src/tcad_agent/remote_protocol/   signed licensed-runner contracts
src/tcad_agent/sentaurus_runner/  reference licensed-host service
skills/                           TCAD operating knowledge
knowledge-sources/                reviewed and review-pending source manifests
examples/                         portable experiment fixtures and prompts
evaluations/                      agent, retrieval, and conformance cases
docs/                             architecture, operations, design, and acceptance
tests/                            unit, integration, and end-to-end verification
```

## Roadmap

### Before the pilot

1. Connect OpenHands file, search, terminal, Git diff, checkpoint, and approval tools to the
   persisted workspace and conversation contracts.
2. Connect the licensed Sentaurus machine and record the exact release and executable identity.
3. Complete the reviewed structure or mesh generation and native-result extraction procedures.
4. Run expert-reviewed golden cases through the signed remote runner.
5. Pass the cross-backend conformance suite without hiding warnings or loosening tolerances
   without approval.
6. Replace exploratory long-term credentials with short-term or role-based production
   authentication.

### After the pilot

1. Add multi-model routing while preserving the same typed model gateway.
2. Expand materials, profiles, studies, and dimensions through portable contracts rather than named-device code.
3. Add domain-expert review workflows and versioned restricted Sentaurus knowledge on the licensed side.
4. Add organization authentication, authorization, quotas, retention, and deployment observability.
5. Build calibration workflows that distinguish exploratory simulation from fabrication-qualified prediction.

## Documentation

- [Technical architecture](docs/architecture.md)
- [Concise product and technical brief](docs/tcad_agent_brief.md)
- [Local web application](docs/operations/local-web-app.md)
- [DEVSIM operations](docs/operations/devsim.md)
- [Sentaurus integration](docs/operations/sentaurus-integration.md)
- [Pilot acceptance](docs/testing/pilot-acceptance.md)
- [Approved platform design](docs/superpowers/specs/2026-09-22-tcad-agent-platform-design.md)

## License

Apache License 2.0. See `LICENSE`.
