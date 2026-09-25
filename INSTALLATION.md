# Quiloo Installation and Setup

This guide installs the complete Quiloo pilot on a Linux workstation. It covers the repository agent, local web interface, Bedrock model access, DEVSIM execution, and the checks needed before a researcher uses the system.

Sentaurus is not installed by these steps. It must remain on a separately licensed host and is connected through Quiloo's restricted remote-runner protocol.

## 1. Supported installation profile

| Component | Supported pilot configuration |
| --- | --- |
| Operating system | Linux workstation with a desktop session, or headless Linux with browser access on the same machine |
| Python | CPython 3.13 |
| Source control | Git |
| Agent model | Amazon Bedrock model available to the configured account and region |
| Local simulator | DEVSIM 2.9.1 in a separate Python environment |
| Licensed simulator | Sentaurus on a separately configured licensed Linux host |

The application binds only to `127.0.0.1`. It is not a multi-user network service and should not be exposed directly to another machine.

## 2. System prerequisites

Install these packages using the workstation's package manager:

- Git
- CPython 3.13, including `venv` support
- a C and C++ build toolchain for packages that do not have a compatible wheel
- `tmux`, recommended for stable long-running agent terminal sessions
- `zenity` or `kdialog`, optional but required for the native desktop folder picker

Example package names on Debian or Ubuntu systems are `git`, `build-essential`, `python3.13`, `python3.13-venv`, `python3.13-dev`, `tmux`, and `zenity`. Python 3.13 may require a distribution release or approved package source that provides it.

Confirm the required tools:

```bash
git --version
python3.13 --version
tmux -V
```

Python must report version 3.13.x. The project intentionally rejects other minor Python versions so the tested OpenHands and scientific dependency set remains reproducible.

## 3. Clone Quiloo

```bash
git clone https://github.com/NovAtom-Labs/Quiloo.git
cd Quiloo
```

For an internal or private deployment, use the organization-approved clone URL and authentication method. Do not place personal access tokens in shell history or repository files.

## 4. Create the Quiloo environment

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install . --no-deps
```

`requirements.txt` is the supported Linux installer entry point. It pins the direct runtime, OpenHands, knowledge, and verification dependencies while allowing pip to select platform-compatible transitive packages. `requirements.lock` records the complete development environment used to verify this checkout. Edit dependency constraints only in `pyproject.toml`; the two requirements files are generated artifacts.

After changing dependencies, regenerate both files on Linux with Python 3.13:

```bash
.venv/bin/python scripts/sync_requirements.py
```

The full refresh deliberately refuses other operating systems and Python minor versions so a developer's machine cannot silently replace the canonical Linux lock. This read-only check is safe on every supported checkout and does not access the network:

```bash
.venv/bin/python scripts/sync_requirements.py --check
```

Confirm the command is installed:

```bash
.venv/bin/tcad-agent --help
```

## 5. Install DEVSIM separately

Keep DEVSIM in a separate environment so simulator packages cannot silently alter the application dependency graph. The default layout places it beside the Quiloo repository:

```text
parent-directory/
  Quiloo/
  devsim/
    .venv/
```

From the Quiloo repository:

```bash
mkdir -p ../devsim
python3.13 -m venv ../devsim/.venv
../devsim/.venv/bin/python -m pip install --upgrade pip
../devsim/.venv/bin/python -m pip install "devsim==2.9.1" numpy
```

Confirm the simulator import and version:

```bash
../devsim/.venv/bin/python -c \
  "import devsim; print('DEVSIM_VERSION=' + devsim.__version__)"
```

Expected output:

```text
DEVSIM_VERSION=2.9.1
```

If DEVSIM is installed elsewhere, record its absolute interpreter path in `TCAD_DEVSIM_PYTHON`. Quiloo invokes that interpreter directly and never executes arbitrary simulator shell text.

## 6. Create the local configuration

Copy the configuration template:

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` and set at least:

```dotenv
AWS_BEARER_TOKEN_BEDROCK=your_local_bedrock_key
AWS_REGION_NAME=ap-south-1
LLM_MODEL=bedrock/global.anthropic.claude-sonnet-4-6
TCAD_REASONING_EFFORT=medium
TCAD_WORKSPACE=.tcad-agent
TCAD_DEVSIM_PYTHON=/absolute/path/to/devsim/.venv/bin/python
```

The model identifier must be available to the configured Bedrock account and region. If the account uses another approved inference profile, replace `LLM_MODEL` with that exact LiteLLM-compatible Bedrock identifier.

Never commit `.env`, credentials, private signing keys, proprietary Sentaurus documents, or licensed examples. Rotate any credential that appears in a prompt, terminal transcript, report, or commit.

The Linux CLI does not implicitly parse `.env`. Load it into the process environment before launching:

```bash
set -a
source .env
set +a
```

Run these three commands again in every new shell unless an approved service manager or environment loader supplies the variables.

## 7. Verify the installation

Run the local checks first:

```bash
OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q
.venv/bin/ruff check src tests
.venv/bin/mypy --strict src
git diff --check
```

On a machine without Bedrock credentials or Sentaurus, the explicitly marked live tests remain skipped. An ordinary test failure is not expected and should be fixed before researchers use the installation.

Verify the DEVSIM execution path:

```bash
.venv/bin/tcad-agent validate examples/pn-junction.yaml
.venv/bin/tcad-agent run examples/pn-junction.yaml \
  --backend devsim \
  --approve \
  --output runs
```

The run must produce a completed evidence bundle whose validation status is `passed`.

## 8. Start the local application

Desktop Linux:

```bash
.venv/bin/tcad-agent serve
```

Headless Linux:

```bash
.venv/bin/tcad-agent serve --no-browser
```

Open the loopback URL printed by the server. The default is `http://127.0.0.1:8765`. If an older process owns that port, Quiloo chooses the next available loopback port and prints it.

The server stores local state under `TCAD_WORKSPACE`, which defaults to `.tcad-agent`. This includes SQLite databases, OpenHands conversation state, event records, compiled jobs, and result bundles. Stop the service before copying this directory for backup.

## 9. Verify the repository agent

Create a disposable scientific repository:

```bash
.venv/bin/python scripts/create_repl_test_repo.py
```

To test approval-gated access outside the selected repository, add `--include-external-fixture`. The generator creates a sibling calibration file that must not be read without an explicit primary-agent approval.

In Quiloo:

1. Select `Open folder` and choose `test-workspaces/pn-junction-research`.
2. Create a conversation.
3. Send this prompt:

```text
Read AGENTS.md and RESEARCH_TASK.md, then complete the research task end to end. Inspect and explain the execution path, run the failing checks, fix root causes only in src/junction_lab, rerun all checks, generate the requested artifacts, review the diff, and delegate one independent read-only physics review before finishing. Stay inside this repository. Do not use network services or git mutations. Do not edit tests, experiment.toml, or reference data.
```

4. Confirm the three-pane layout. At desktop width, resize both dividers and double-click each one to restore its default. At tablet width, open Repository as a drawer. At narrow width, open Agent as a drawer.
5. Use Chat for the conversation and approval decisions. Inspect the plain-language explanation before opening Technical details. Approve all like this applies only to the displayed permission category and expires when the run ends.
6. Use Activity to inspect one expandable row per tool action, including phase, delegated ownership, duration, commands, and output. Current-operation summaries are derived from tool events. Raw provider reasoning is never stored or displayed.
7. Use Changes to confirm that only the files attributable to this run appear. Select a changed text file and verify that its unified diff opens in the central workspace.
8. Open a safe text file, select Edit, make a disposable change, and save it. Restore that manual edit before grading so it is not confused with agent work.
9. Wait for the final response, then run the deterministic grader:

```bash
.venv/bin/python evaluations/repl/grade_workspace.py \
  --workspace test-workspaces/pn-junction-research
```

Expected evidence includes five passing tests, corrected source code, generated JSON and Markdown artifacts, unchanged researcher-owned inputs, a delegated review result, and a grader score of 100. The run-scoped Changes view should list exactly `src/junction_lab/physics.py`, `src/junction_lab/report.py`, and `src/junction_lab/validation.py` for the deterministic repair scenario.

## 10. Verify the TCAD agent workflow

Open a repository workspace, create an Agent conversation, and paste the prompt in
`examples/prompts/al-pn-al-equilibrium.md`. Ask the agent to inspect the request, prepare the
portable specification, check DEVSIM capabilities, run only the explicit supported subset, and
report the generated evidence.

The local DEVSIM subset uses ohmic contacts, Boltzmann statistics, constant mobility, and SRH.
Aluminum work functions, Fermi statistics, Auger recombination, band-gap narrowing, band profiles,
mobility output, and recombination output remain visible as unsupported local capabilities.

The full request is represented by `examples/al-pn-al-equilibrium.yaml` for the Sentaurus adapter.
Licensed execution must remain unavailable until the remote host passes the Sentaurus integration
and conformance checklist.

## 11. Optional Bedrock smoke test

Run this only after loading a valid local credential:

```bash
OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest \
  tests/e2e/test_agentic_repl.py \
  --run-live-bedrock -m live_bedrock -q
```

A model configuration error usually means the credential, region, or inference profile does not match. Provider details are deliberately excluded from researcher-facing error messages so secrets are not leaked.

## 12. Sentaurus connection

Do not install Sentaurus into the Quiloo application environment. Follow `docs/operations/sentaurus-integration.md` on the licensed machine. The connection requires an approved HTTPS endpoint, exact release identity, reviewed structure generation, native-result extraction, signing keys, quotas, and cross-backend conformance cases.

Quiloo must continue to refuse licensed execution until that integration is explicitly configured and verified.

## 13. Troubleshooting

### Native folder picker does not open

Install `zenity` or `kdialog`. On headless Linux, enter the absolute repository path in the workspace screen.

### The server starts on another port

An older or different build owns the requested port. Use the exact URL printed by the new process, or stop the old process before restarting.

### The model is unavailable

Confirm that `.env` was loaded, the key was created for `AWS_REGION_NAME`, and `LLM_MODEL` names an inference profile available to that account. Do not print the credential while debugging.

### DEVSIM cannot be found

Run the DEVSIM import check directly and set `TCAD_DEVSIM_PYTHON` to the absolute path of the interpreter that succeeds.

### A run waits for approval

Review the exact command or path in the approval card. External paths, package installation, network access, destructive commands, Git mutation, and unknown actions require a decision. Do not approve an action merely to make the run continue.

### A run is paused after restart

Select Resume. Conversation state and events are persisted, but interrupted work is not silently restarted.

### Sentaurus reports unconfigured

This is the safe default. Compilation can be inspected locally, but execution requires the separately licensed and verified remote host.

## 14. Upgrade procedure

Before upgrading, stop the local server and back up `.env` and `TCAD_WORKSPACE` outside the repository. Then:

```bash
git pull --ff-only
.venv/bin/python scripts/sync_requirements.py --check
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install . --no-deps
OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q
```

Restart the service only after the verification suite passes. Do not weaken dependency pins or validation checks to force an upgrade through.
