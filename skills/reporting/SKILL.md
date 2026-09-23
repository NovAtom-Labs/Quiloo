---
name: reporting
description: Use when producing a technical report or researcher-facing summary from a completed TCAD experiment bundle.
---

# Reporting Experiment Evidence

Structured evidence owns every scientific claim.

1. Call `build_report` with the normalized specification, canonical result, validation report, citations, and provenance.
2. Copy numeric values only from canonical fields. Include units and terminal or spatial context.
3. Show failed and warning validators without softening their status.
4. Separate computed findings, cited background, assumptions, and limitations.
5. Label uncalibrated simulations exploratory and include reproduction instructions.

Do not derive numbers from prose or logs. Do not describe a failed run as completed.

Evidence required: bundle ID, simulator and adapter versions, hashes, validation table, citations, and limitations.
