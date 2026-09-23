---
name: specification
description: Use when translating a semiconductor research request into an ExperimentSpec or deciding which scientific details require clarification.
---

# Building Experiment Specifications

Turn researcher intent into data, never simulator syntax.

1. Extract geometry, material, profiles, contacts, equations, physical models, study, observables, units, and bounds.
2. Ask for missing information only when it changes the experiment materially. Never guess units, contact placement, material, or physical models.
3. Build `ExperimentSpec` without a device-type field. Named devices are descriptions, not execution modes.
4. Call `validate_spec`. Resolve every schema, unit, topology, and reference issue before capability checking.
5. Present normalized assumptions and the planned study for approval before execution.

Refuse a request outside the published dimensional or physics envelope. Return the unsupported field and the nearest supported boundary.

Evidence required: normalized specification, clarification answers, schema version, and validation result.
