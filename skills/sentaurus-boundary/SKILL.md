---
name: sentaurus-boundary
description: Use when compiling, executing, retrieving guidance for, or comparing results from the licensed Sentaurus backend.
---

# Operating the Sentaurus Boundary

Sentaurus is a licensed remote backend, not a prompt dialect.

1. Require the exact deployed Sentaurus version, configured remote runner, and a supported capability decision.
2. Retrieve only version-compatible licensed guidance from the controlled index.
3. Send the same portable `ExperimentSpec` used by DEVSIM to the deterministic Sentaurus adapter.
4. Submit signed compiled artifacts through the remote runner protocol. Never send free-form shell commands.
5. Normalize native output into `CanonicalResult`, then run the same validators and report builder used for DEVSIM.
6. Run conformance comparisons with per-case expert tolerances. Expect semantic agreement, not identical meshes or values.

Refuse to invent Scheme, Tcl, SDevice syntax, model mappings, or result parsers when licensed version-specific evidence is unavailable. Refuse execution when the remote endpoint is unconfigured.

Evidence required: Sentaurus version, licensed source IDs, compiler and runner versions, signed hashes, native logs, normalized result, and conformance report.
