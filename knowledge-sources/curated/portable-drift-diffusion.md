# Portable Drift-Diffusion Foundations

Status: machine-curated foundation, awaiting TCAD domain-lead review.

Scope: one-dimensional, isothermal, nondegenerate silicon drift-diffusion studies using electrostatic potential plus electron and hole continuity equations. This guide explains model intent. Backend compilers remain authoritative for simulator syntax.

## Minimum physical state

The electrostatic state is potential, electron density, hole density, ionized donor density, ionized acceptor density, permittivity, and temperature. The portable specification expresses donor and acceptor concentrations as nonnegative quantities. A backend may form signed net doping as donor concentration minus acceptor concentration.

Poisson's equation connects potential to charge density. Electron and hole continuity equations connect carrier accumulation, transport, and generation-recombination. A DC steady-state solve has no transient accumulation term, but still requires both continuity equations when both carriers are transported.

## Units

Researcher inputs must carry units. The portable contract normalizes length to SI meters, concentration to inverse cubic meters, temperature to kelvin, voltage to volts, electric field to volts per meter, and current density to amperes per square meter.

Simulator adapters may convert units internally. DEVSIM examples commonly use centimeters and inverse cubic centimeters. The adapter owns these conversions. An LLM must not convert by editing generated backend code.

For one-dimensional simulations, terminal output is current density unless an explicit cross-sectional area exists in the scientific specification. Never label current density as total current.

## Geometry and profiles

One-dimensional regions are ordered intervals. Adjacent boundaries must be contiguous. Each profile references a region by ID. Constant donor and acceptor profiles are composable and do not imply a named device class.

An intrinsic-like region in a practical numerical fixture may contain a very small background concentration. That is not physically identical to zero doping. Reports must preserve the actual value from the specification.

## Contacts and bias

The current foundation supports one contact at each end of the one-dimensional domain. An ohmic contact fixes carrier relationships and electrostatic boundary behavior through deterministic backend equations. Contact semantics are not merely a voltage label.

A DC sweep names the biased contact and carries start, stop, and positive step voltages. The number of requested points is inclusive: `(stop - start) / step + 1`. A compiler must use decimal-safe or otherwise deterministic stepping so requested endpoints are not lost to floating-point accumulation.

## Equilibrium and continuation

Equilibrium is the preferred initial state for a drift-diffusion sweep. A robust DC workflow solves electrostatics, establishes carrier equilibrium, then continues through ordered bias points. Each converged point may initialize the next point.

If a bias point fails, numerical recovery may reduce the step, restart from equilibrium, or continue from the last converged point. Recovery must not change geometry, doping, material, contacts, equations, or requested observables without researcher approval.

## What the current model does not establish

A numerically converged drift-diffusion result is not automatically fabrication-predictive. Mobility, recombination, statistics, band structure, interfaces, dimensionality, and material parameters must match the intended regime and be calibrated against suitable measurements or trusted references. The current foundation is exploratory and silicon-first.

## Source basis

- portable schema: `src/tcad_agent/domain/models.py`
- DEVSIM mapping: `src/tcad_agent/adapters/devsim/compiler.py`
- pinned DEVSIM source: commit `43b41ca845184c47e22b72d144db7e7db8509377`
- this guide contains no Sentaurus syntax or proprietary documentation
