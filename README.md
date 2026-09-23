# NovAtom TCAD Agent

NovAtom TCAD Agent is a simulator-neutral foundation for researcher-driven semiconductor device simulation. Researchers describe regions, doping profiles, contacts, physics, studies, and observables in a strict `ExperimentSpec`. Deterministic adapters translate that data into simulator inputs. DEVSIM works locally today. Sentaurus is represented by the same capability and execution contracts and remains disabled until the licensed machine is connected.

Named devices are examples, not execution modes. The PN and PIN examples pass through the same schema, compiler, runner, normalizer, validators, bundle writer, and report generator. A researcher can compose another supported one-dimensional silicon stack without adding product code.

## Current status

Working now:

- strict units-aware experiment specifications
- data-driven backend capability checks and explicit refusal
- deterministic DEVSIM compilation and bounded execution
- canonical results, physical checks, immutable evidence bundles, and reports
- manifest-gated local knowledge retrieval with citations
- eight TCAD operating skills and a typed OpenHands tool boundary
- researcher CLI with an explicit execution approval gate

Deliberate limits:

- one-dimensional, silicon-first structures
- constant donor and acceptor profiles
- ohmic contacts, equilibrium, and bounded DC sweeps
- exploratory output, not fabrication-calibrated prediction
- no Sentaurus execution until its licensed machine, exact version, adapter, and runner are configured

See [Architecture](docs/architecture.md), [DEVSIM operations](docs/operations/devsim.md), and [Sentaurus integration](docs/operations/sentaurus-integration.md).

## Quick start

Python 3.13 is required. From this repository:

```bash
/usr/local/bin/python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install . --no-deps
.venv/bin/pytest -q
```

Validate both ordinary data fixtures:

```bash
.venv/bin/tcad-agent validate examples/pn-junction.yaml
.venv/bin/tcad-agent validate examples/pin-diode.yaml
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

The agent profile exposes only the `tcad_domain` tool. It does not expose a terminal. Simulation execution requires an approved plan identifier in agent workflows or `--approve` in the CLI.

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
skills/                      progressive TCAD operating knowledge
examples/                    ordinary experiment fixtures
evaluations/                 retrieval and cross-backend acceptance cases
```
