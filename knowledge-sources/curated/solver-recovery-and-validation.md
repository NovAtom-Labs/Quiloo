# Solver Recovery and Result Validation

Status: machine-curated foundation, awaiting TCAD domain-lead review.

## Failure classes

Classify evidence before changing anything:

- specification failure: invalid units, topology, references, or bounds
- capability failure: unsupported dimension, physics, material, study, or observable
- execution failure: missing executable, license failure, nonzero exit, timeout, or transport failure
- initialization failure: equilibrium or starting state does not converge
- continuation failure: a later bias point fails after earlier points converge
- mesh failure: discretization is invalid or demonstrably insufficient
- parser failure: expected native output is missing or malformed
- physical-validation failure: the solver exits successfully but results violate mandatory checks

These classes require different responses. Retrying a missing license or unsupported equation is not solver recovery.

## Bounded numerical recovery

Permitted recovery changes numerics while preserving scientific intent. Examples are equilibrium restart, smaller bias steps, continuation from the last converged point, or bounded mesh refinement. Preserve the failed attempt and create a new plan. Limit automatic attempts and stop when the same classified failure repeats.

Forbidden automatic changes include doping concentration, region dimensions, material, contact semantics, temperature, physical models, equations, and requested observables.

## Mandatory result checks

Execution success is necessary but insufficient. Validate the canonical result for:

1. completed execution and a native result artifact
2. exact expected sweep point count
3. convergence at every reported point
4. finite numeric values
5. ordered and complete bias values
6. terminal current conservation within declared tolerances
7. physically admissible carrier densities
8. simulator, compiler, input, runtime, and artifact provenance

The overall result is the worst mandatory check. A failed mandatory check forces a failed bundle even when the simulator return code is zero.

## Cross-backend comparison

DEVSIM and Sentaurus may use different discretizations, nonlinear methods, defaults, and model implementations. Conformance therefore compares semantic outputs and selected expert-owned metrics, not raw deck text or identical meshes.

Before comparing values, align units, terminal orientation, bias definition, physical models, temperature, geometry, and parameter values. Use both absolute and relative tolerances near zero. Record the tolerance owner and reference case version.

## Evidence preservation

Every attempt needs normalized input, compiled artifacts, stdout, stderr, native result, canonical result, validation report, versions, hashes, and a human-readable report. Never overwrite a failed bundle with a successful retry.

## Source basis

- `src/tcad_agent/runners/models.py`
- `src/tcad_agent/validation/engine.py`
- `src/tcad_agent/bundles/writer.py`
- `evaluations/conformance/cases.yaml`
