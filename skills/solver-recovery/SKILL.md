---
name: solver-recovery
description: Use when a supported TCAD job fails numerically, times out, or returns nonconverged bias points.
---

# Recovering Solver Failures

Recovery may change numerics, not scientific intent.

1. Classify the evidence as execution, mesh, initialization, stepping, convergence, or physical-validation failure.
2. Stop immediately for missing licenses, malformed compiled artifacts, unsupported physics, or inconsistent specifications.
3. Select one approved numerical action: smaller bias step, equilibrium restart, continuation from the last converged point, or bounded mesh refinement.
4. Create a new execution plan and preserve the failed attempt. Never overwrite its logs or bundle.
5. Run at most three recovery attempts. Stop sooner if the same classified failure repeats.
6. Re-run every validator after recovery.

Never change doping, materials, contact semantics, equations, or requested observables without researcher approval.

Evidence required: failure class, selected policy, attempt number, changed numerical fields, and before-and-after validation reports.
