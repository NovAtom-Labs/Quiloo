# Local Researcher Web App

## Start it

1. Install the project and DEVSIM as described in the README.
2. Copy `.env.example` to `.env`.
3. Put a valid Bedrock credential in `.env`. Do not paste it into source, a prompt, a report, or Git.
4. Double-click `launch_tcad_agent.command` in Finder.
5. The browser opens `http://127.0.0.1:8765`.

The launcher binds only to `127.0.0.1`. If a healthy instance is already running, it reuses it instead of starting a second server.

You can also start it from a terminal:

```bash
.venv/bin/tcad-agent-web
```

## Researcher workflow

1. Paste a research problem and select DEVSIM or Sentaurus.
2. Answer only the displayed consequential questions, such as missing layer thickness or contact treatment.
3. Review the normalized specification, capability result, warnings, and exact plan digest.
4. Approve that plan.
5. Run once. Repeated Run clicks return the existing terminal state and do not create duplicate simulator jobs.
6. Inspect stage events, validation results, the Markdown report, canonical result, native output, and manifest hashes.

The interface shows stage progress, not hidden model reasoning.

## Backend behavior

DEVSIM runs locally now. Use `examples/al-pn-al-equilibrium-devsim.yaml` for the explicit local approximation of the Al / p-Si / n-Si / Al request.

Sentaurus can compile locally, but execution must stop as unconfigured until the licensed runner is connected. The full request is `examples/al-pn-al-equilibrium.yaml`.

Unsupported physics or observables must be visible. Do not silently remove them. If a researcher accepts an approximation, it must produce a new exact plan and a new approval.

## Local data

`TCAD_WORKSPACE` controls the SQLite request database, event ledgers, compiled jobs, and bundles. The default is `.tcad-agent` in the repository. Artifacts are local unless a configured licensed runner receives a signed Sentaurus job.

## Troubleshooting

- `model_configuration_error`: check the local Bedrock credential, region, and model ID. The response intentionally hides provider details and secrets.
- `backend_unsupported`: review the exact unsupported fields and select only an explicit approved approximation.
- `backend_unconfigured`: Sentaurus compilation may be available, but licensed execution is not connected.
- DEVSIM executable missing: set `TCAD_DEVSIM_PYTHON` to the installed DEVSIM environment.
- failed validation: inspect the validation report and preserve the bundle. The system does not relabel a converged but unphysical result as successful.

