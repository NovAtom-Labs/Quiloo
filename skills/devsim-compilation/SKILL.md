---
name: devsim-compilation
description: Use when compiling an approved, capability-supported ExperimentSpec for the local DEVSIM backend.
---

# Compiling for DEVSIM

The deterministic adapter owns all DEVSIM syntax.

1. Require a validated specification, supported capability decision, and execution approval.
2. Call `compile_experiment` with backend `devsim`.
3. Preserve the returned input digest, runtime digest, compiler version, and complete generated inputs.
4. Execute only the returned entrypoint through `run_experiment` with an explicit budget.

Do not write or patch DEVSIM Python from conversation text. If compilation refuses a feature, return the capability issue. If the compiler itself lacks a supported mapping, report an adapter defect instead of inventing an equation.

Evidence required: compiler version, both hashes, generated files, simulator version, stdout, and stderr.
