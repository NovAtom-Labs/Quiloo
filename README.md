# Quiloo

Quiloo is NovAtom Labs' simulator-neutral TCAD research agent. It turns a researcher's natural-language device study into a strict experiment specification, asks only for consequential missing inputs, presents the exact normalized plan for approval, runs an allowed simulator workflow, validates the numerical output, and packages reproducible evidence.

The pilot runs DEVSIM locally. The same researcher workflow and portable `ExperimentSpec` are designed to target a licensed Sentaurus installation through a restricted remote runner. Simulator-specific syntax, execution, and normalization stay behind adapters, so devices are described as data instead of hardcoded product modes.

> **Pilot status:** the local DEVSIM workflow is operational. Sentaurus compilation, signing, normalization, and conformance infrastructure are implemented, but licensed execution remains intentionally disabled until the licensed machine passes the integration checklist.

## Why Quiloo

General-purpose language models are useful for interpreting research intent, but they are not reliable authorities for TCAD syntax, physical support, units, or numerical validity. Quiloo separates those responsibilities:

- The model interprets the request and proposes structured scientific intent.
- A strict schema owns units, geometry, doping, contacts, physics, studies, and observables.
- Backend manifests decide whether DEVSIM or Sentaurus can represent the request.
- Deterministic compilers generate simulator inputs.
- Bounded runners execute only approved jobs.
- Validators, not the model, decide whether produced evidence passes.
- A versioned knowledge layer supplies reviewed TCAD context with citations.

The model never emits simulator code directly into execution and never receives a terminal tool.

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

In the local web application, the researcher:

1. Describes the intended device study and selects a backend.
2. Answers missing values that affect the physical structure or boundary conditions.
3. Reviews normalized geometry, doping, contacts, study parameters, equations, models, observables, backend, and declared limitations.
4. Approves the immutable plan digest.
5. Runs the simulation.
6. Reviews validation results and downloads the evidence bundle.

Repeated Run actions return the existing terminal state. They do not create duplicate simulator jobs.

## What works now

| Area | Current capability |
| --- | --- |
| Research interface | Local, loopback-only web application with clarification, plan review, approval, execution, validation, and artifact downloads |
| Portable specification | Strict one-dimensional `ExperimentSpec` with dimensional quantities and rejection of unknown fields |
| Structures | Composable ordered silicon regions, without named-device execution branches |
| Doping | Constant donor and acceptor profiles |
| Contacts | DEVSIM ohmic contacts; Sentaurus ohmic and explicit metal work-function mappings |
| Studies | Equilibrium and bounded DC sweeps |
| DEVSIM | Deterministic compilation, local subprocess isolation, normalization, validation, reports, and evidence bundles |
| Sentaurus | Deterministic `sdevice.cmd` compilation, source maps, hashes, signed remote protocol, strict result normalization, and conformance rules |
| Knowledge | Manifest-gated retrieval with source metadata, review state, backend/version filters, content hashes, and citations |
| Agent boundary | Eight TCAD skills and one typed `tcad_domain` tool; no terminal exposed to the model |
| Recovery | Bounded, allowlisted recovery policy with explicit failure classification |
| Auditability | Persistent request states, immutable plan digests, event ledgers, artifact SHA-256 values, and atomic bundles |

## Deliberate pilot limits

Quiloo is currently intended for small exploratory drift-diffusion studies, architecture validation, and researcher workflow testing. It is not yet a fabrication-calibrated prediction system.

The current boundary is:

- one-dimensional, silicon-first structures
- constant doping profiles
- equilibrium and bounded DC studies
- manifest-declared equations, models, contacts, and observables only
- no arbitrary user or model-generated simulator syntax
- no two-dimensional process geometry, heteromaterials, optical coupling, thermal coupling, hydrodynamic transport, or production calibration unless explicitly added through the portable contracts
- no real Sentaurus execution until the licensed host, exact release, mesh procedure, native extraction, restricted knowledge, and golden conformance cases are reviewed

Unsupported physics is reported explicitly. It is never silently removed to make a run pass.

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
| `web` | Minimal local researcher application |

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

- macOS or Linux for the current local launcher and runner workflow
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

The pilot template currently selects the global Claude Sonnet 5 Bedrock inference profile in `ap-south-1`. A Bedrock API key must be generated in the same region. Keep credentials only in `.env` or a secret manager.

Never commit `.env`, API keys, signing keys, proprietary manuals, licensed examples, or generated local workspaces. Revoke and rotate any credential disclosed in a prompt, chat, log, report, or commit.

## Run the local web application

On macOS, double-click:

```text
launch_tcad_agent.command
```

Or start it from a terminal:

```bash
.venv/bin/tcad-agent-web
```

The application binds only to [http://127.0.0.1:8765](http://127.0.0.1:8765). If a healthy instance is already running, the launcher reuses it.

For the main pilot demonstration, paste [the Al / p-Si / n-Si / Al prompt](examples/prompts/al-pn-al-equilibrium.md), select DEVSIM, and answer the requested thickness and contact questions. The local approximation is explicit about unsupported work-function and advanced-physics behavior.

## CLI examples

Validate portable specifications:

```bash
.venv/bin/tcad-agent validate examples/pn-junction.yaml
.venv/bin/tcad-agent validate examples/pin-diode.yaml
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
| `examples/al-pn-al-equilibrium-devsim.yaml` | Explicit DEVSIM approximation of the pilot metal-contact equilibrium problem |
| `examples/al-pn-al-equilibrium.yaml` | Full Sentaurus-targeted form with work functions and advanced requested models |

Researchers can compose other supported one-dimensional silicon stacks by changing data. No named-device branch is required.

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
  validation/report.json
  report.md
  manifest.json
  events.jsonl
```

Validation covers execution status, convergence, point counts, finite values, sweep ordering, terminal conservation, carrier bounds, requested-output completeness, and provenance. Mandatory failure produces a failed bundle state. Reports read structured results only; logs remain evidence and are not treated as a numeric source of truth.

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

1. Connect the licensed Sentaurus machine and record the exact release and executable identity.
2. Complete the reviewed structure or mesh generation and native-result extraction procedures.
3. Run expert-reviewed golden cases through the signed remote runner.
4. Pass the cross-backend conformance suite without hiding warnings or loosening tolerances without approval.
5. Replace exploratory long-term credentials with short-term or role-based production authentication.

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
