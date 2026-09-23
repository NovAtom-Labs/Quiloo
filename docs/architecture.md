# Architecture

## Design objective

The stable product is the simulator-neutral experiment and evidence workflow. DEVSIM and Sentaurus are replaceable execution backends. LLM output never becomes simulator code or a shell command.

The core flow is:

```text
research request
  -> ExperimentSpec
  -> schema and semantic validation
  -> backend capability decision
  -> researcher approval
  -> deterministic adapter
  -> bounded runner
  -> canonical result
  -> validation
  -> immutable evidence bundle and report
```

Retrieval supports specification and explanation, but it cannot override the schema, capability manifest, approval gate, compiler, or validators.

## Stable contracts

### ExperimentSpec

`ExperimentSpec` is the only scientific intent passed into a backend. It contains one-dimensional ordered regions, dimensional quantities, profiles, boundary contacts, equations and models, a study, and requested observables. It rejects unknown fields and invalid units. It intentionally has no `device_type` field.

This gives researchers composability without a script per device. The existing PN and PIN files differ only in their data. A three-region detector-like stack, asymmetric junction, or other supported structure uses the same path.

### CapabilityManifest

Each backend publishes dimensions, equations, models, materials, profiles, contacts, studies, observables, and resource limits. Capability decisions return `supported`, `needs_input`, `backend_unsupported`, or `platform_unsupported`, with exact issue paths. `execution_state` is separate from scientific capability so an unavailable license is never misreported as unsupported physics.

### Adapter

Every adapter implements three operations:

```python
manifest -> CapabilityManifest
compile(spec, workspace) -> CompiledJob
normalize(native_run) -> CanonicalResult
```

The compiler is deterministic. Its job records the exact entrypoint, arguments, environment, input files, input digest, runtime digest, and compiler version. Free-form generated simulator syntax is forbidden.

### Runner

Runners execute a `CompiledJob` under a `RunBudget` and return a `NativeRunResult`. They use argument arrays, never a shell. The local runner applies timeout and file boundaries. The remote runner accepts only signed, backend-specific job artifacts and an allowlisted service endpoint.

### CanonicalResult and validation

All native output is normalized before scientific checks or reporting. Validators check execution, convergence, point count, finite values, sweep order, terminal conservation, carrier bounds, and provenance. A mandatory failure forces a failed bundle state.

### Experiment bundle

Bundle creation is atomic. A completed run contains:

```text
<run-id>/
  experiment.json
  compiled/               generated backend inputs
  logs/stdout.log
  logs/stderr.log
  native/native_result.json
  results/canonical.json
  validation/report.json
  report.md
  manifest.json           versions, state, digests, and artifact SHA-256 values
```

Reports read structured data only. Logs remain evidence, not a source of numeric claims.

## Agent boundary

OpenHands receives eight small skills for specification, capability checks, DEVSIM compilation, recovery, validation, citation, reporting, and Sentaurus policy. Its custom `tcad_domain` tool exposes typed actions only. The production profile does not expose a terminal. The agent may propose a plan, but execution remains approval-gated.

This separation makes the model replaceable. Model reasoning helps interpret intent and choose tools. Deterministic software owns units, support, simulator syntax, execution, checks, provenance, and output.

## Knowledge boundary

Sources enter through a versioned manifest with source ID, title, URL or controlled location, license, access class, trust level, backend, version, review status, and optional local path. Only allowlisted text formats are indexed. Each passage has a content hash and every hit returns a citation.

Public DEVSIM source can be indexed locally. Proprietary Sentaurus documents must remain on the licensed machine or another approved restricted store. They must not be committed or sent to a model provider unless the license and company policy explicitly permit it.

## Adding scope without hardcoding devices

To add a new material, profile, contact, study, or observable:

1. Extend the portable schema only if the concept is simulator-neutral.
2. Add the capability value to each backend that truly supports it.
3. Add a deterministic mapping inside each supporting adapter.
4. Add normalization and mandatory validation for the new output.
5. Add data fixtures and conformance tolerances.
6. Add reviewed knowledge sources when model guidance is required.

Do not add named-device branches. If a new structure is expressible with existing concepts, add only an example or evaluation case.

## Current boundary

The foundation is intentionally one-dimensional and silicon-first. It is suitable for validating the architecture and automating small exploratory drift-diffusion studies. It is not a calibrated process or device-design authority. Two-dimensional geometry, arbitrary profiles, heteromaterials, advanced transport, process simulation, optical coupling, thermal coupling, and pilot access control require later scoped work.
