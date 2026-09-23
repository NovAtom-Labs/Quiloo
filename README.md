# NovAtom TCAD Agent

NovAtom TCAD Agent is a simulator-neutral research workflow for semiconductor device simulation. A researcher can enter a natural-language request in a local web application, answer consequential clarification questions, review an exact plan, approve it, run DEVSIM locally, and inspect a validated evidence bundle. The same strict `ExperimentSpec` can be compiled by the Sentaurus adapter without changing the researcher workflow. Licensed Sentaurus execution remains disabled until its separate machine is configured and reviewed.

Named devices are examples, not execution modes. The PN and PIN examples pass through the same schema, compiler, runner, normalizer, validators, bundle writer, and report generator. A researcher can compose another supported one-dimensional silicon stack without adding product code.

## Current status

Working now:

- strict units-aware experiment specifications
- data-driven backend capability checks and explicit refusal
- deterministic DEVSIM compilation and bounded execution
- local browser interface with clarification, plan approval, run progress, reports, and downloads
- persistent request lifecycle, duplicate-run protection, and a tamper-evident event ledger
- bounded failure classification and allowlisted recovery decisions
- deterministic Sentaurus Device command compilation with source mapping and hashes
- signed remote-runner protocol with replay, path, size, version, and output controls
- strict Sentaurus result normalization and case-scoped cross-backend conformance
- canonical results, physical checks, immutable evidence bundles, and reports
- manifest-gated local knowledge retrieval with citations, injected into each model request
- backend-specific TCAD skill context and clarification answers injected into the model request
- eight TCAD operating skills and a typed OpenHands tool boundary
- researcher CLI and web app with an explicit execution approval gate

Deliberate limits:

- one-dimensional, silicon-first structures
- constant donor and acceptor profiles
- DEVSIM: ohmic contacts, equilibrium, bounded DC sweeps, and the manifest-declared model subset
- Sentaurus compiler: ohmic or metal work-function contacts and the reviewed model mappings
- exploratory output, not fabrication-calibrated prediction
- no real Sentaurus execution until the licensed machine supplies a reviewed structure or mesh artifact, exact release, restricted knowledge, endpoint identity, and golden conformance run

See [Local web app](docs/operations/local-web-app.md), [DEVSIM operations](docs/operations/devsim.md), [Sentaurus integration](docs/operations/sentaurus-integration.md), and [Pilot acceptance](docs/testing/pilot-acceptance.md).

## Quick start

Python 3.13 is required. From this repository:

```bash
/usr/local/bin/python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install . --no-deps
.venv/bin/pytest -q
```

For the normal researcher workflow, copy `.env.example` to `.env`, add a valid Bedrock credential, and double-click `launch_tcad_agent.command`. The app is available only on `http://127.0.0.1:8765`.

Validate both ordinary data fixtures:

```bash
.venv/bin/tcad-agent validate examples/pn-junction.yaml
.venv/bin/tcad-agent validate examples/pin-diode.yaml
.venv/bin/tcad-agent validate examples/al-pn-al-equilibrium-devsim.yaml
.venv/bin/tcad-agent validate examples/al-pn-al-equilibrium.yaml
```

Inspect a natural-language agent evaluation prompt:

```bash
.venv/bin/tcad-agent evaluation show metal-silicon-junction-equilibrium
```

Run a study only after reviewing it:

```bash
.venv/bin/tcad-agent run examples/pn-junction.yaml \
  --backend devsim \
  --approve \
  --output runs
```

Compile the full Sentaurus example without requiring the licensed runner:

```bash
.venv/bin/tcad-agent compile examples/al-pn-al-equilibrium.yaml \
  --backend sentaurus \
  --output compiled/al-pn-al-sentaurus
```

Compilation is available offline. Execution remains blocked until the licensed runner is configured.

Build the local DEVSIM knowledge index from the approved manifest:

```bash
.venv/bin/tcad-agent knowledge build \
  --manifest knowledge-sources/manifests/sources.yaml \
  --root "/Users/satyagni/Documents/NovAtom Labs"

.venv/bin/tcad-agent knowledge search "ohmic contact equation" \
  --backend devsim \
  --version 2.9.1
```

The installed DEVSIM runtime is `2.9.1` at `/Users/satyagni/Documents/NovAtom Labs/devsim/.venv`. Its Apache-2.0 source checkout is pinned at commit `43b41ca845184c47e22b72d144db7e7db8509377` in `/Users/satyagni/Documents/NovAtom Labs/devsim/source`.

## Configuration

- `LLM_MODEL`: OpenHands/LiteLLM model identifier. Pilot default: `bedrock/global.anthropic.claude-sonnet-5`.
- `TCAD_REASONING_EFFORT`: OpenHands reasoning effort. Default: `medium`.
- `AWS_BEARER_TOKEN_BEDROCK`: Amazon Bedrock API key. Keep it only in the ignored local `.env` file or a secret manager.
- `AWS_REGION_NAME`: Bedrock invocation region. The local pilot uses `ap-south-1` with the global Sonnet 5 inference profile.
- `TCAD_DEVSIM_PYTHON`: optional DEVSIM Python executable override. The default is the sibling `devsim/.venv/bin/python` path.
- `TCAD_WORKSPACE`: optional local request database and artifact root. Default: `.tcad-agent`.
- `TCAD_SENTAURUS_ENDPOINT`, `TCAD_SENTAURUS_VERSION`, and signing key variables are deployment-only settings for the licensed runner. They are not required for DEVSIM.

Create the local configuration from the safe template, add the credential, and
export it before starting an agent process:

```bash
cp .env.example .env
set -a
source .env
set +a
```

Never commit `.env`. Rotate any credential that has been disclosed outside the
local secret store.

The agent profile exposes only the `tcad_domain` tool. It does not expose a terminal. The model proposes structured intent only. Deterministic code performs capability checks, compilation, execution, validation, recovery decisions, and reporting. Simulation execution requires approval of the exact plan digest.

The knowledge build combines the pinned public DEVSIM source with NovAtom's curated portable TCAD guides. Curated guides are explicitly marked as awaiting domain-lead review. Sentaurus guidance remains closed until version-compatible licensed sources are available on the licensed machine.

## Repository layout

```text
src/tcad_agent/domain/       portable experiment contract
src/tcad_agent/capabilities/ backend support and refusal
src/tcad_agent/adapters/     deterministic simulator translations
src/tcad_agent/runners/      bounded local and remote execution boundaries
src/tcad_agent/results/      canonical simulator-neutral results
src/tcad_agent/validation/   numerical and physical checks
src/tcad_agent/bundles/      immutable evidence packaging
src/tcad_agent/knowledge/    authorized ingestion and retrieval
src/tcad_agent/agent/        typed OpenHands tools and runtime profile
src/tcad_agent/control/      request lifecycle, approval, and orchestration
src/tcad_agent/web/          loopback-only researcher application
src/tcad_agent/remote_protocol/ signed licensed-runner contracts
src/tcad_agent/sentaurus_runner/ reference licensed-host service
skills/                      progressive TCAD operating knowledge
examples/                    ordinary experiment fixtures
evaluations/                 retrieval and cross-backend acceptance cases
```
