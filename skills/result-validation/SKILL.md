---
name: result-validation
description: Use when deciding whether simulator output is numerically and physically acceptable for reporting.
---

# Validating TCAD Results

Convergence is necessary but not sufficient.

1. Call `validate_result` on the canonical result, never directly on a native log.
2. Check execution status, expected point count, convergence, finite values, sweep order, terminal conservation, carrier bounds, and provenance.
3. Treat the overall result as the worst mandatory check.
4. A failed check remains visible in the report and blocks a successful bundle state.
5. Compare reference metrics only with case-specific, expert-approved tolerances.

Do not waive a validator in narrative text. A waiver requires a versioned validation configuration and named human approval.

Evidence required: check IDs, levels, measured values, limits, statuses, and evidence paths.
