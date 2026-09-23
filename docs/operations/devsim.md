# DEVSIM Operations

## Installed runtime

- Python: 3.13
- DEVSIM package: 2.9.1
- executable: `/Users/satyagni/Documents/NovAtom Labs/devsim/.venv/bin/python`
- source: `/Users/satyagni/Documents/NovAtom Labs/devsim/source`
- source commit: `43b41ca845184c47e22b72d144db7e7db8509377`

DEVSIM has its own virtual environment so product dependencies and simulator dependencies cannot silently alter each other.

If the simulator is not in the sibling `devsim` directory, set `TCAD_DEVSIM_PYTHON` to its absolute Python executable path.

## Validate, compile, and run

```bash
.venv/bin/tcad-agent validate examples/pn-junction.yaml

.venv/bin/tcad-agent compile examples/pn-junction.yaml \
  --backend devsim \
  --output compiled

.venv/bin/tcad-agent run examples/pn-junction.yaml \
  --backend devsim \
  --approve \
  --timeout-seconds 120 \
  --output runs
```

Validation is safe and read-only. Compilation writes deterministic inputs but does not start the simulator. Run requires `--approve` and writes a new immutable bundle. Reusing a run ID is rejected by the bundle writer.

## Inspect a run

The CLI prints the final bundle directory. Check `manifest.json` first. A usable result requires:

- bundle `state` is `completed`
- native and canonical statuses are completed
- validation `overall` is `passed`
- simulator, compiler, input, and runtime identities are present
- every artifact hash matches its file

Print the report with:

```bash
.venv/bin/tcad-agent report runs/<run-id>
```

The current one-dimensional compiler reports terminal current density in `A/m^2`. It does not infer a device area or total current.

## Build and query local knowledge

```bash
.venv/bin/tcad-agent knowledge build \
  --manifest knowledge-sources/manifests/sources.yaml \
  --root "/Users/satyagni/Documents/NovAtom Labs"

.venv/bin/tcad-agent knowledge search "ohmic drift diffusion contact" \
  --backend devsim \
  --version 2.9.1
```

The index is immutable. Delete an obsolete generated index only when intentionally rebuilding from a newly reviewed manifest. The index directory is ignored by Git.

## Failure handling

- `invalid specification`: correct schema, units, topology, or references before capability checking.
- `backend_unsupported`: do not weaken physics silently. Return the exact unsupported field.
- timeout or nonconvergence: preserve the failed evidence, then use one bounded numerical recovery such as smaller voltage steps or equilibrium restart.
- failed physical validation: treat the bundle as failed even if DEVSIM returned exit code zero.
- malformed native result: preserve stdout and stderr and fix the deterministic parser or compiler. Do not extract values from prose.

## Verification

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest -q
```

Integration tests invoke the separately installed DEVSIM runtime. Unit tests remain simulator-independent.
