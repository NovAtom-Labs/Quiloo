# Specification and Capability Guide

Status: machine-curated foundation, awaiting TCAD domain-lead review.

## Separate intent from implementation

An experiment specification describes scientific intent. It must not contain DEVSIM Python, Sentaurus Tcl or Scheme, executable paths, shell commands, solver log fragments, or model-generated code.

The current schema requires:

- schema version and experiment name
- dimension
- ordered material regions with dimensional coordinates
- profiles with species, region, and dimensional concentration
- contacts with stable IDs, locations, and kinds
- equations, physical models, and temperature
- equilibrium or DC study
- requested observables
- optional string metadata

Unknown fields are rejected. This prevents a misspelled or hallucinated control from being silently ignored.

## No device taxonomy in execution

There is deliberately no `device_type`, `pn_diode`, `pin_diode`, `moscap`, or `mosfet` execution field. Names may help humans, but the solver path depends only on composition. If a requested structure can be expressed with existing regions, profiles, contacts, physics, and studies, it requires new data, not new product code.

## Clarification rules

Clarify missing information when it changes the experiment materially. Never guess units, material, contact position, bias terminal, transport equations, physical models, temperature, or desired observable.

Minor prose differences that normalize to the same explicit specification do not need separate device modes. Present normalized assumptions before execution approval.

## Capability is data

Every backend manifest declares supported dimensions, equations, models, materials, profiles, contacts, studies, observables, and limits. Check capability only after schema and semantic validation.

Outcomes have distinct meanings:

- `supported`: the backend declares every requested feature.
- `needs_input`: intent is incomplete and researcher input is required.
- `backend_unsupported`: the simulator adapter does not declare a requested feature.
- `platform_unsupported`: the product contract does not yet represent the request.

Backend execution configuration is separate. Sentaurus can be scientifically capable but operationally unconfigured because the licensed runner is unavailable.

## Refusal quality

A useful refusal names the exact field path, requested value, and supported boundary. It never removes requested physics or substitutes a simpler model silently. A researcher-approved simplification becomes a new specification and a separately recorded plan.

## Extension checklist

Add a simulator-neutral feature to the schema, then update each genuinely supporting capability manifest, compiler mapping, normalizer, validator, data fixture, and conformance case. A feature is not complete when only one generated deck happens to run.

## Source basis

- `src/tcad_agent/domain/models.py`
- `src/tcad_agent/capabilities/models.py`
- `src/tcad_agent/capabilities/service.py`
- `src/tcad_agent/adapters/base.py`
