---
name: capability-checking
description: Use when selecting a simulator backend or determining whether requested TCAD physics and observables are supported.
---

# Checking Backend Capability

Use manifests as authority. Model knowledge is not a capability declaration.

1. Start with a schema-valid `ExperimentSpec`.
2. Call the capability tool for each candidate backend.
3. Treat `supported`, `needs_input`, `backend_unsupported`, and `platform_unsupported` as distinct outcomes.
4. For backend mismatches, name the exact field and supported values. Recommend another backend only when its manifest supports the request.
5. Check execution configuration separately. A backend may support a feature while its licensed runner is unavailable.

Never remove requested physics merely to make a check pass. Any researcher-approved simplification becomes a new specification and a new validation record.

Evidence required: backend, manifest version, decision status, and every issue path.
