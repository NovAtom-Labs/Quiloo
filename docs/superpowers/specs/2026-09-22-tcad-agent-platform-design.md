# NovAtom TCAD Agent Platform Design

**Status:** Design baseline for review  
**Date:** 2026-09-22  
**Initial simulator:** DEVSIM  
**Pilot simulator:** Synopsys Sentaurus Device through a remote licensed runner  
**Agent runtime:** OpenHands Software Agent SDK  

## 1. Executive summary

NovAtom will build a research-facing TCAD agent that converts a natural-language research request into a reproducible, validated simulation study and an auditable engineering report.

The product is not a collection of hard-coded device workflows. Researchers describe geometry, materials, doping, contacts, physical models, bias conditions, outputs, and success criteria. The system converts that request into a simulator-neutral `ExperimentSpec`, validates it against an explicit capability envelope, compiles it for a selected simulator, executes it, checks numerical and physical validity, and reports the evidence.

DEVSIM is the development backend because it is open, scriptable in Python, and suitable for rapid local iteration. Sentaurus Device is the required pilot backend. Sentaurus runs on a separate licensed machine behind a narrow remote job API. The agent, user interface, experiment specification, validation system, and reporting system do not depend on either simulator.

The first release is intentionally broad in composition but bounded in physics. It supports researchers creating varied, low-to-moderate complexity semiconductor devices from reusable primitives. It refuses unsupported or under-specified work rather than inventing physics. A PN diode, MOS capacitor, and planar MOSFET are reference evaluations only. They are not special product modes.

The knowledge gap of general-purpose LLMs is addressed through four separate mechanisms:

1. Structured registries for facts that must be exact.
2. Retrieval-augmented generation over authoritative, versioned sources.
3. OpenHands skill files for procedural TCAD behavior.
4. Deterministic compilers, validators, and simulator execution for truth.

The recommended initial model is Claude Sonnet 5 on Amazon Bedrock with medium adaptive reasoning for the full pilot workflow. It offers the best expected balance of agentic reasoning and cost for the single-model pilot, subject to the platform acceptance set. Model choice remains configuration, never architecture.

## 2. Product definition

### 2.1 Product promise

Given a research request within the supported capability envelope, the system will:

1. Interpret the scientific intent.
2. Ask only questions required to remove consequential ambiguity.
3. Produce a typed, unit-safe experiment specification.
4. Show the proposed assumptions and study plan before expensive execution.
5. Compile the same specification for DEVSIM or Sentaurus.
6. Run simulations in an isolated and observable environment.
7. Recover from bounded numerical failures using approved strategies.
8. Validate numerical convergence and basic physical consistency.
9. Generate plots, extracted metrics, limitations, citations, and provenance.
10. Save a reproducible experiment bundle that another researcher can rerun.

### 2.2 Intended users

The primary user is a semiconductor researcher or device engineer who understands the device under study but should not need to remember every simulator command or deck syntax.

The system assists scientific work. It does not replace expert review, process calibration, or sign-off for fabrication decisions.

### 2.3 Initial capability envelope

The first release should support:

- One-dimensional and two-dimensional device structures.
- Rectangular and polygonal regions with explicit interfaces.
- Semiconductor, dielectric, and conductor regions.
- Constant, piecewise, Gaussian, and imported tabular doping profiles.
- Ohmic contacts and idealized gate contacts.
- Electrostatic Poisson solves.
- Classical drift-diffusion transport.
- Fermi-Dirac or Boltzmann statistics where supported and mapped.
- A small approved set of mobility and recombination models.
- Equilibrium and DC bias sweeps.
- Terminal current, charge, potential, electric field, carrier density, and derived scalar metrics.
- Parameter sweeps with explicit bounds and budgets.
- Silicon-first material coverage, with additional materials added only through reviewed material packs.

The capability envelope is declared by data and adapter manifests. It is not implied by what the LLM believes a simulator can do.

### 2.4 Explicit non-goals for the first release

- Arbitrary process simulation.
- Three-dimensional production structures.
- Full electrothermal or optical coupling.
- Quantum transport, NEGF, Monte Carlo, or hydrodynamic transport.
- Unreviewed compound-semiconductor polarization, trap, or tunneling models.
- Automatic calibration to confidential fab data.
- Fabrication-ready predictive claims.
- Free-form execution of LLM-generated shell commands on the Sentaurus machine.
- Exact numerical equality between different simulators.
- Fine-tuning a TCAD foundation model during the initial build.

## 3. Design principles

### 3.1 The LLM proposes. Typed software decides. Simulators compute.

The LLM handles intent interpretation, planning, explanation, and bounded repair selection. It does not define truth. Schema validation, unit checking, capability checks, deterministic compilation, simulator execution, and numerical validators are authoritative.

### 3.2 Devices are compositions, not code paths

There must be no orchestration branches such as `if device_type == "mosfet"`. A device is a graph of regions, boundaries, contacts, material assignments, profiles, models, studies, and observables.

Named device examples can exist as ordinary `ExperimentSpec` fixtures, tutorials, and evaluations. They cannot receive privileged behavior.

### 3.3 Backend-neutral core, backend-specific edges

No OpenHands prompt, researcher-facing API, or validation workflow may depend on DEVSIM Python or Sentaurus syntax. Backend syntax exists only inside an adapter and its compiler tests.

### 3.4 Refuse unsupported science

The system must distinguish:

- Supported and sufficiently specified.
- Supported but missing required information.
- Representable in the specification but unsupported by the chosen backend.
- Outside the platform capability envelope.

The last two states produce a clear refusal or a backend recommendation. They never trigger best-effort script invention.

### 3.5 Every result carries evidence

Every reported result must identify:

- The normalized experiment specification.
- Material and model parameter sources.
- Simulator name and exact version.
- Adapter and compiler versions.
- Generated input artifacts and hashes.
- Solver logs and exit status.
- Convergence and validation results.
- Any agent actions taken during recovery.
- Known limitations and unresolved warnings.

### 3.6 Reproducibility is a product feature

An experiment is complete only when its bundle can be rerun without the original conversation.

## 4. Recommended architecture

```text
Researcher
    |
    v
Research API / Minimal UI
    |
    v
OpenHands Orchestrator
    |  uses skills, retrieval, and typed tools
    v
Intent Parser -> Clarification Gate -> ExperimentSpec Builder
                                      |
                                      v
                         Schema, Unit, and Capability Validator
                                      |
                         +------------+------------+
                         |                         |
                         v                         v
                  DEVSIM Adapter            Sentaurus Adapter
                         |                         |
                         v                         v
                Local Sandbox Runner       Remote Licensed Runner
                         |                         |
                         +------------+------------+
                                      |
                                      v
                         Canonical Result Normalizer
                                      |
                                      v
                    Numerical and Physical Validation Engine
                                      |
                         +------------+------------+
                         |                         |
                    Repair Loop                Report Builder
                         |                         |
                         +------------> Experiment Bundle
```

The architecture uses one agent loop with deterministic tools. Multiple personas or subagents are not required for the pilot. Specialized behavior belongs in tools and skills, which are easier to evaluate and control.

## 5. Core domain model

### 5.1 `ResearchRequest`

The original user request plus structured metadata:

- Scientific objective.
- Requested device or structure description.
- Requested studies and observables.
- Constraints and parameter ranges.
- Preferred simulator, if any.
- Accuracy and runtime preference.
- User-provided files and references.

The original text is retained unchanged for auditability.

### 5.2 `ExperimentSpec`

`ExperimentSpec` is the canonical intermediate representation. It is serialized as versioned JSON or YAML and validated by a strict schema.

Top-level sections:

```yaml
schema_version: "1.0"
metadata:
  title: "Example study"
  purpose: "Research question in one sentence"
  assumptions: []
units:
  length: "um"
  concentration: "cm^-3"
  temperature: "K"
geometry:
  dimensions: 2
  regions: []
  interfaces: []
materials: []
profiles: []
contacts: []
mesh:
  global: {}
  refinements: []
physics:
  equations: []
  statistics: {}
  mobility: []
  recombination: []
studies: []
observables: []
validators: []
execution:
  backend: "auto"
  limits: {}
```

The actual schema must use tagged unions and explicit enums where possible. Unknown fields are rejected. Every physical quantity carries a unit. Defaults are recorded after normalization and never applied silently.

### 5.3 `CapabilityManifest`

Each backend publishes a machine-readable manifest containing:

- Supported dimensions.
- Geometry features.
- Mesh features.
- Materials available through reviewed packs.
- Equations and physical models.
- Study types.
- Boundary and contact types.
- Observable mappings.
- Solver controls.
- Known incompatibilities.
- Backend version constraints.

The planner intersects the experiment requirements with this manifest before compilation.

### 5.4 `ExecutionPlan`

The deterministic planner expands an accepted `ExperimentSpec` into ordered stages:

1. Geometry construction.
2. Mesh generation.
3. Material and profile assignment.
4. Equilibrium solve.
5. Transport initialization.
6. Bias continuation.
7. Requested sweeps.
8. Result extraction.
9. Validation runs, including mesh refinement when requested.

The LLM may propose plan changes, but the planner validates them against approved transitions and run budgets.

### 5.5 `CanonicalResult`

Every backend maps native output into a common result model:

- Coordinates and mesh metadata.
- Region, boundary, and contact identities.
- Named scalar and field quantities with units.
- Terminal data indexed by study point.
- Solver diagnostics per step.
- Warnings and failure classification.
- Provenance hashes.

Canonical results allow backend-independent validation and reporting.

### 5.6 `ExperimentBundle`

Each run produces an immutable directory or object-store bundle:

```text
experiment.json
request.txt
plan.json
capability-snapshot.json
sources.json
generated/
native-output/
canonical-results/
validation.json
plots/
report.md
events.jsonl
manifest.json
```

`manifest.json` contains hashes for all files and the complete version chain.

## 6. Agent design with OpenHands

### 6.1 Agent responsibility

The OpenHands agent performs five reasoning tasks:

1. Translate research intent into candidate structured fields.
2. Detect consequential ambiguity and ask focused questions.
3. Select relevant knowledge and procedural skills.
4. Choose among approved recovery actions after failures.
5. Explain results, evidence, and limitations.

It does not directly edit native simulator decks during normal operation.

### 6.2 Typed tool surface

Expose a small set of custom tools with structured inputs and outputs:

- `search_tcad_knowledge(query, filters)`
- `get_material(material_id, version)`
- `get_model(model_id, backend)`
- `validate_experiment(spec)`
- `compare_backend_capabilities(spec, backends)`
- `compile_experiment(spec, backend)`
- `estimate_run(plan, backend)`
- `run_experiment(compiled_id, limits)`
- `inspect_run(run_id, selectors)`
- `validate_results(run_id, validator_set)`
- `apply_recovery(run_id, recovery_action)`
- `build_report(run_id)`

Tools return typed status codes, compact evidence, and artifact references. They must not dump entire logs into the model context.

### 6.3 Agent state machine

```text
REQUESTED
  -> NEEDS_CLARIFICATION
  -> SPEC_DRAFTED
  -> SPEC_VALIDATED
  -> USER_CONFIRMATION_REQUIRED
  -> COMPILED
  -> RUNNING
  -> VALIDATING
  -> REPAIRABLE_FAILURE -> RUNNING
  -> SUCCEEDED_WITH_WARNINGS
  -> SUCCEEDED
  -> REFUSED
  -> FAILED
```

The agent cannot skip schema validation, capability validation, user confirmation for material assumptions, or result validation.

### 6.4 Recovery policy

Recovery is an allowlisted policy, not unrestricted experimentation. Initial recovery actions can include:

- Reduce a bias step.
- Insert additional continuation points.
- Restart from the last converged state.
- Increase iteration limits within a cap.
- Change an approved damping parameter.
- Apply a predefined mesh refinement rule.
- Re-run equilibrium initialization.

Each recovery has preconditions, a maximum attempt count, and an audit event. The agent may select an action but cannot invent a new solver manipulation at runtime.

## 7. Knowledge architecture

### 7.1 Why RAG alone is insufficient

RAG improves access to documentation, but retrieved text can be stale, ambiguous, irrelevant to the installed simulator version, or physically inappropriate. Therefore the system uses four knowledge classes with different authority.

| Knowledge class | Examples | Storage | Authority |
|---|---|---|---|
| Exact structured facts | units, material parameters, model compatibility, backend capability | versioned JSON/YAML registries | highest before simulator execution |
| Procedural knowledge | how to initialize, sweep bias, diagnose divergence | OpenHands `SKILL.md` files | instructions, not scientific truth |
| Explanatory reference | manuals, examples, papers, internal notes | hybrid RAG index | supporting context with citations |
| Empirical evidence | solver output, validation metrics, benchmark results | experiment bundles and evaluation store | highest for a particular run |

The agent must cite retrieved sources in plans and reports. A retrieved fact cannot silently override a structured registry.

### 7.2 Four-day knowledge bootstrap

The first useful knowledge layer must be buildable in three to four focused days.

#### Day 1: Acquire and normalize authoritative sources

Ingest only sources with clear provenance:

- The DEVSIM manual for the installed version.
- DEVSIM command reference.
- Official DEVSIM examples and golden results.
- DEVSIM source documentation relevant to Python APIs.
- Internal NovAtom TCAD notes approved by a researcher.
- Textbooks or papers only when legally available and specifically relevant.
- Sentaurus documentation only on the licensed machine and only under license-compliant access controls.

For every document, store source URI, title, publisher, version, retrieval date, license classification, checksum, and access scope.

Do not scrape random forums into the authoritative index. Forum content can enter a separate low-trust collection only after expert review.

#### Day 2: Build retrieval and structured registries

Create:

- Section-aware document chunks of roughly 400 to 900 tokens.
- Parent-child links from chunks to manual sections and documents.
- Code chunks aligned to complete functions or examples.
- Metadata filters for simulator, version, topic, command, physics model, material, and trust level.
- Hybrid retrieval using BM25 plus embeddings.
- A lightweight reranker or model-based reranking over the top candidates.
- A minimal silicon material registry with units and citations.
- A model compatibility registry for the initial capability envelope.

Keep code and prose in separate indexes or strongly typed collections. A question about command syntax should prefer version-matched command documentation and executable examples.

#### Day 3: Write procedural skill files

Create narrow OpenHands skills with progressive disclosure:

```text
skills/
  tcad-request-clarification/SKILL.md
  tcad-experiment-planning/SKILL.md
  tcad-meshing/SKILL.md
  tcad-drift-diffusion/SKILL.md
  tcad-bias-continuation/SKILL.md
  tcad-convergence-recovery/SKILL.md
  tcad-result-validation/SKILL.md
  tcad-reporting/SKILL.md
  devsim-backend/SKILL.md
  sentaurus-backend/SKILL.md
```

Each skill states:

- When it applies.
- Required inputs.
- Ordered procedure.
- Allowed decisions.
- Stop and refusal conditions.
- Tools to call.
- Evidence required before completion.
- Links to small supporting references.

Skills contain procedures, not large pasted manuals. OpenHands supports progressive disclosure for `SKILL.md`, so only the skill description remains in baseline context and full instructions load when needed.

#### Day 4: Add golden examples and measure retrieval

Create 25 to 40 questions covering:

- Command syntax.
- Model selection.
- Units and parameter provenance.
- Geometry and boundary setup.
- Convergence diagnosis.
- Interpretation of common outputs.
- Unsupported requests.

For each question, record required source chunks and an expert-approved short answer. Measure retrieval recall at 5, citation correctness, answer faithfulness, and refusal behavior. Fix metadata and chunking before adding more documents.

### 7.3 RAG query pipeline

1. Classify the query as syntax, physics, material, workflow, failure, or interpretation.
2. Extract simulator and version constraints.
3. Query the matching collections using lexical and semantic search.
4. Apply trust and version filters.
5. Rerank the top results.
6. Return short passages with stable source identifiers.
7. Require the agent to attach source identifiers to claims.
8. Log the query, retrieved chunks, final claims, and downstream outcome.

### 7.4 Knowledge update policy

- All sources are immutable after ingestion.
- A changed source creates a new version.
- Material and physics registry changes require researcher review.
- Skill changes require scenario tests.
- Retrieval index builds receive a unique version.
- Every experiment records the exact registry, skill, and index versions used.
- Successful agent trajectories do not automatically become knowledge.
- Candidate learnings enter a review queue before promotion.

### 7.5 Sentaurus knowledge boundary

Sentaurus documents and examples must remain on infrastructure authorized by the license. The remote runner may expose a retrieval endpoint that returns only permitted excerpts or structured answers. It must enforce authentication, authorization, logging, and document-level access rules.

Do not copy proprietary Sentaurus manuals into a public repository, third-party vector service, or external LLM prompt unless the applicable agreement permits it.

## 8. Backend adapter contract

Every simulator adapter implements the same interface:

```text
capabilities() -> CapabilityManifest
validate(spec) -> ValidationReport
compile(spec) -> CompiledExperiment
estimate(compiled) -> ResourceEstimate
execute(compiled, limits) -> NativeRunResult
normalize(native_result) -> CanonicalResult
diagnose(native_result) -> FailureReport
version() -> BackendVersion
```

### 8.1 Compiler requirements

- Deterministic output for identical normalized inputs and compiler version.
- No network access during compilation.
- Stable formatting to support snapshot tests and review.
- Source mapping from generated deck lines to `ExperimentSpec` paths.
- Static rejection of unsupported constructs.
- Explicit naming rules to avoid backend identifier collisions.
- No execution of user-provided code fragments.

### 8.2 DEVSIM adapter

The DEVSIM adapter compiles the specification into Python and associated mesh files. It runs in a pinned container or reproducible environment containing the exact DEVSIM version.

Initial mappings cover:

- Geometry and mesh creation.
- Region, interface, and contact construction.
- Material parameters.
- Poisson and drift-diffusion equations.
- Contact boundary conditions.
- Equilibrium initialization.
- DC continuation and sweeps.
- Contact current and charge extraction.
- Field and carrier export.
- Solver diagnostic capture.

DEVSIM allows user-defined PDE models and provides extensive control. The adapter must expose only the reviewed subset represented by the capability manifest.

### 8.3 Sentaurus adapter

The Sentaurus adapter compiles the same specification into the required Sentaurus Structure Editor or mesh artifacts, Sentaurus Device command files, and job metadata.

The adapter lives with the main codebase when licensing permits, but execution occurs on the licensed machine. If generated artifacts are also license-sensitive, compilation occurs remotely.

Backend-specific features may be represented as namespaced extensions:

```yaml
extensions:
  sentaurus:
    approved_feature: value
```

Extensions must never be necessary for a backend-neutral experiment. Using one marks the experiment as non-portable and the UI must show that fact.

### 8.4 Remote Sentaurus runner

The remote service exposes a narrow authenticated API:

- Submit a signed compiled job bundle.
- Query job status.
- Cancel a job.
- Retrieve allowlisted logs and results.
- Query installed simulator and adapter versions.
- Query the capability manifest.

It does not expose an arbitrary remote shell.

Required controls:

- Mutual TLS or an equivalent strong service identity.
- Short-lived job credentials.
- Per-user and per-project authorization.
- CPU, memory, wall-time, disk, and concurrency quotas.
- Isolated job directories.
- Command allowlisting.
- Input hash verification.
- Complete audit logs.
- Secret and license-server isolation.
- Result retention and deletion policy.

## 9. Simulator portability and parity

Portability means semantic equivalence within declared limits, not identical decks or identical numbers.

### 9.1 Portable core

An experiment is portable when:

- Every requested feature exists in both capability manifests.
- Materials and model parameters have compatible definitions.
- Boundary conditions have equivalent semantics.
- Requested outputs can be normalized into the same canonical quantities.
- Validation tolerances account for discretization and implementation differences.

### 9.2 Cross-backend conformance suite

Use a ladder of ordinary experiment fixtures:

1. One-dimensional electrostatic structure.
2. One-dimensional PN junction at equilibrium.
3. PN junction DC sweep.
4. MOS capacitor electrostatic and C-V study.
5. Two-dimensional planar MOSFET transfer and output studies.

For each case, compare:

- Geometry and region semantics.
- Material and model configuration.
- Bias sequence.
- Qualitative trends.
- Selected scalar metrics with justified tolerances.
- Conservation residuals.
- Mesh refinement behavior.

These fixtures validate the platform. They do not constrain what researchers may compose.

## 10. Validation framework

### 10.1 Validation levels

#### Level 0: Specification validity

- Schema validity.
- Unit consistency.
- Geometric integrity.
- Contact and region connectivity.
- Required parameter presence.
- Capability compatibility.

#### Level 1: Execution validity

- Process exited normally.
- Every required study point completed.
- Solver reported convergence.
- No NaN or infinite values.
- Output shapes and units are valid.

#### Level 2: Numerical validity

- Residual and update norms meet policy.
- Terminal current conservation is within tolerance.
- Bias continuation is continuous.
- Selected quantities stabilize under mesh refinement.
- Results do not depend excessively on an initial guess.

#### Level 3: Physical sanity

- Carrier densities are non-negative and finite.
- Electrostatic and terminal trends match declared expectations.
- Current direction and bias polarity are consistent.
- Equilibrium terminal currents are near zero within tolerance.
- Extracted metrics fall inside declared broad physical bounds.

#### Level 4: Reference comparison

- Compare against an analytical solution, published benchmark, golden run, or second backend when available.

### 10.2 Validation result

Each validator returns:

- `PASS`, `WARN`, `FAIL`, or `NOT_APPLICABLE`.
- Measured value and threshold.
- Evidence artifact.
- Explanation.
- Suggested approved recovery action, if one exists.

A converged solver result is not automatically a successful experiment.

## 11. Researcher workflow

### 11.1 Request

The researcher provides a plain-language objective and may attach geometry, tabular profiles, parameter ranges, or reference data.

### 11.2 Clarification

The system asks about only decisions that materially change the experiment, such as dimensions, material, temperature, contact behavior, physical models, bias range, or required outputs.

### 11.3 Plan review

Before execution, the interface shows:

- A concise device and study summary.
- Assumptions and their sources.
- Unsupported or approximated requests.
- Selected models.
- Planned sweeps.
- Estimated run scale.
- Validation checks.
- Target backend and portability status.

The researcher approves or edits the structured plan.

### 11.4 Execute and observe

The UI streams stage-level progress, not raw agent monologue. It shows solver progress, warnings, recovery attempts, cost, and remaining run budget.

### 11.5 Report

The final report contains:

- Objective.
- Device and study definition.
- Assumptions.
- Physics and parameter sources.
- Backend and versions.
- Results and plots.
- Extracted metrics.
- Validation table.
- Recovery actions.
- Limitations.
- Reproduction instructions.

## 12. API and service boundaries

Recommended services for the pilot:

### 12.1 Control API

Owns users, projects, experiment lifecycle, agent conversations, approvals, and artifact references.

### 12.2 Knowledge service

Owns source ingestion, hybrid search, citations, registry lookup, and knowledge versioning.

For a very small team, this can begin as a module inside the control API with a clean interface. It does not need an independent deployment on day one.

### 12.3 Compiler package

A pure Python package containing the schema, normalization, capability validation, adapter contracts, and deterministic compilers.

### 12.4 Runner service

Executes compiled work in a sandbox and returns native artifacts. DEVSIM and Sentaurus runners share a protocol but use different deployments.

### 12.5 Validation package

Consumes only `ExperimentSpec`, `CanonicalResult`, and validation configuration. It has no dependency on an LLM.

### 12.6 Report package

Builds a deterministic technical report from normalized data, validator output, citations, and a limited LLM-written narrative. Numeric tables and claims come from structured inputs.

## 13. Model recommendation

### 13.1 Primary recommendation

Use **Claude Sonnet 5 on Amazon Bedrock** as the single production agent model for the pilot.

Configuration:

- Model ID: `bedrock/global.anthropic.claude-sonnet-5` through the OpenHands and LiteLLM provider path.
- Reasoning effort: `medium` adaptive thinking for the complete pilot workflow.
- Output verbosity: low or medium.
- Typed tool calls plus deterministic schema validation for every domain object.
- Prompt caching: enabled for stable skill and schema context.
- Maximum agent steps: bounded by workflow state and per-run budget.

Why:

- Sonnet 5 is designed for coding, agents, and professional work at scale.
- It supports tool use, adaptive reasoning, prompt caching, and a one-million-token context on Bedrock.
- Current standard API pricing is $2 per million input tokens and $10 per million output tokens.
- It costs half as much per token as GPT-5.6 Sol while remaining suitable for complex agent work.
- A single model simplifies evaluation during the pilot. Deterministic validators provide the second line of defense instead of another LLM.

This recommendation is provisional until Sonnet 5 passes the platform acceptance set on the actual Bedrock and OpenHands integration.

### 13.2 Model acceptance gate

Run the same 30 to 50 representative tasks with a pinned model snapshot when available. A candidate must meet:

- At least 95 percent syntactically valid tool calls.
- At least 90 percent valid `ExperimentSpec` drafts after one repair.
- Zero silent execution of unsupported physics.
- At least 90 percent correct source selection on the knowledge set.
- At least 85 percent successful completion on supported end-to-end tasks.
- No regression in numeric claim grounding.
- Median cost and latency within the pilot budget.

If Sonnet 5 fails this gate, evaluate **GPT-5.6 Sol on Amazon Bedrock** as the higher-cost fallback.

### 13.3 Models not recommended as the initial single model

| Model | Reason not selected for the initial default |
|---|---|
| GPT-6 Astra | Highest capability, but $10 input and $50 output per million tokens is unnecessary before the workflow and validators mature. |
| GPT-5.6 Sol | Higher capability ceiling, but twice Sonnet 5's standard token price. Consider only if the acceptance set shows a meaningful completion-rate gain. |
| GPT-5.6 Luna | Excellent cost, but should first be evaluated for routine classification and extraction. It is too risky as the only reasoning model for scientific planning. |
| GPT-5.5 | Superseded for this pilot by the newer Bedrock candidates. |
| Claude Opus 4.8 | More expensive and unnecessary until an internal TCAD evaluation proves a clear benefit. |
| Gemini 3.8 Flash | Attractive price and agent focus, but use only after direct evaluation of structured tool reliability and TCAD reasoning in this harness. |
| Local open-weight model | Useful later for private retrieval or cheap extraction. Current tool-use variance adds avoidable pilot risk. |

### 13.4 Cost controls

- Never place full manuals in the prompt.
- Use progressive skill loading.
- Retrieve small source passages with metadata filters.
- Summarize native logs deterministically before model review.
- Cache stable schema and skill content.
- Set a token, tool-call, simulation, and wall-time budget per experiment.
- Stop repeated failure loops after the approved recovery budget.
- Record cost by workflow stage and task type.

## 14. Security, IP, and scientific governance

### 14.1 Execution security

- Run DEVSIM in an isolated container with no default network access.
- Run Sentaurus through the narrow remote runner.
- Treat uploaded files and retrieved text as untrusted input.
- Do not allow prompt content to expand tool permissions.
- Separate agent credentials from simulator and license credentials.
- Sign job bundles and verify hashes at the runner.

### 14.2 Knowledge and licensing

- Track the license and permitted use of every ingested source.
- Keep proprietary sources in an access-controlled index.
- Do not send proprietary excerpts to external providers without approval.
- Make citation and source visibility obey user permissions.

### 14.3 Scientific governance

- Material packs and physical model mappings require researcher review.
- Every published result shows validation status and limitations.
- Failed validators cannot be hidden by narrative text.
- The report labels uncalibrated simulations as exploratory.
- Human approval is required before results are used for fabrication or external claims.

## 15. Evaluation strategy

### 15.1 Evaluation layers

1. **Schema tests:** valid and invalid specification fixtures.
2. **Compiler tests:** deterministic snapshots and native syntax checks.
3. **Adapter tests:** backend capability and error mapping.
4. **Solver tests:** known simulations with frozen environments.
5. **Validator tests:** injected failures and expected classifications.
6. **Retrieval tests:** source recall, ranking, citations, and version filtering.
7. **Agent tests:** request-to-spec, clarification quality, recovery choice, and refusal.
8. **End-to-end tests:** request-to-report on both backends.
9. **Expert review:** blind scoring by device researchers.

### 15.2 Reference evaluation suite

The diode, MOS capacitor, and MOSFET are useful because they exercise progressively more of the platform. They remain ordinary input fixtures.

Add composition-focused cases that are not named devices:

- Multi-region electrostatic stacks.
- Nonuniform doping profiles.
- Asymmetric contacts.
- Geometry parameter sweeps.
- Mesh refinement requests.
- Requests with missing units.
- Requests for unsupported physics.
- Contradictory requests.
- Backend-specific capability mismatches.

### 15.3 Pilot acceptance criteria

The pilot is ready when:

- At least 20 varied supported research requests complete end to end.
- At least 90 percent of supported requests produce a valid specification without engineer editing after clarification.
- All reported scalar values trace to canonical result fields.
- Every scientific claim has either computed evidence or a citation.
- Unsupported requests are refused reliably.
- The conformance suite passes on both DEVSIM and Sentaurus.
- Cross-backend metric differences remain within per-case expert-approved tolerances.
- Every run produces a complete reproducible bundle.
- A researcher can create a new in-envelope device without changing product code.
- The system completes the customer-facing planar MOSFET study without hidden manual intervention.

## 16. Implementation sequence

### Phase 0: Four-day knowledge and feasibility sprint

Deliver:

- Version-pinned DEVSIM environment.
- Source manifest and first retrieval index.
- Initial structured silicon and model registries.
- Eight to ten procedural skill files.
- Retrieval evaluation set.
- One manual DEVSIM experiment represented in a draft `ExperimentSpec`.

Exit condition: the agent can answer scoped DEVSIM questions with citations and produce a schema-valid draft without executing arbitrary code.

### Phase 1: Simulator-neutral vertical slice

Deliver:

- `ExperimentSpec` v1.
- Capability manifest schema.
- Unit and semantic validation.
- DEVSIM compiler for a narrow drift-diffusion subset.
- Local runner.
- Canonical result format.
- Basic report.

Exit condition: two structurally different experiments run through the same path with no device-specific orchestration.

### Phase 2: Validation and recovery

Deliver:

- Layered validators.
- Failure taxonomy.
- Approved recovery policy.
- Mesh refinement checks.
- Experiment bundles and event logs.

Exit condition: injected numerical failures are detected, classified, and either repaired within budget or reported honestly.

### Phase 3: Researcher experience

Deliver:

- Natural-language request interface.
- Clarification flow.
- Plan review and approval.
- Progress view.
- Technical report and artifact download.

Exit condition: a researcher unfamiliar with the implementation can create and inspect an in-envelope experiment.

### Phase 4: Sentaurus adapter and remote runner

Deliver:

- License-compliant remote service.
- Sentaurus capability manifest.
- Deterministic compiler.
- Native result normalization.
- Version-scoped Sentaurus knowledge access.
- Cross-backend conformance results.

Exit condition: the same portable `ExperimentSpec` runs on both backends and passes its defined validation tolerances.

### Phase 5: Pilot hardening

Deliver:

- Frozen model and prompt versions.
- Full acceptance evaluation.
- Cost and latency dashboard.
- Access controls and audit review.
- Backup and retention policy.
- Pilot runbook.

Exit condition: all pilot acceptance criteria pass on the exact deployment intended for demonstration.

## 17. Recommended repository structure

```text
tcad-agent/
  apps/
    api/
    web/
  packages/
    domain/
      schemas/
      units/
      capabilities/
    compiler/
      core/
      devsim/
      sentaurus/
    runners/
      protocol/
      local_devsim/
      remote_sentaurus/
    validation/
    reporting/
    knowledge/
    agent/
  registries/
    materials/
    physics/
    validators/
  skills/
  knowledge-sources/
    manifests/
  evaluations/
    retrieval/
    agent/
    conformance/
    end_to_end/
  examples/
  docs/
```

Keep schemas, adapters, validators, and tools in separate packages. A package should expose a small typed interface and should be testable without starting OpenHands.

## 18. Key risks and mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| The LLM creates plausible but invalid physics | Misleading research results | Typed registries, capability gates, deterministic validators, citations, expert review |
| The platform becomes three hard-coded demos | No researcher generality | Composition-based schema, generic compiler, varied fixture suite, no device branches |
| Backend abstraction collapses to the lowest common denominator | Weak Sentaurus value | Portable core plus explicit namespaced extensions and portability labels |
| DEVSIM and Sentaurus disagree | Loss of trust | Semantic mapping review, case-specific tolerances, qualitative and conservation checks |
| RAG retrieves stale or wrong-version guidance | Invalid commands or models | Version filters, trust levels, citations, immutable index versions |
| Agent loops become expensive | Poor pilot economics | Compact tool outputs, progressive skills, caching, strict budgets, recovery caps |
| Sentaurus licensing is violated | Legal and commercial risk | Remote controlled index and runner, access controls, legal review |
| Scope expands into advanced devices too early | Schedule failure | Published capability envelope, refusal behavior, staged material and model packs |
| A result converges but is physically wrong | False confidence | Multi-level validation, mesh checks, reference comparisons, warning visibility |

## 19. Decisions fixed by this design

1. The product is a bounded research platform, not a three-device demo.
2. Devices are data compositions and evaluation fixtures, not hard-coded workflows.
3. `ExperimentSpec` is the stable product contract.
4. DEVSIM and Sentaurus are replaceable backend adapters.
5. Sentaurus executes through a remote licensed runner before the pilot.
6. RAG, skills, registries, and execution evidence have distinct roles.
7. The first knowledge layer is deliberately buildable in four days.
8. The LLM cannot bypass validation or capability checks.
9. The initial physics envelope is silicon-first, classical, one-dimensional and two-dimensional, equilibrium and DC.
10. Advanced physics enters through reviewed capabilities, not prompt changes.
11. The initial system uses one primary LLM and deterministic validation rather than an unnecessary multi-agent hierarchy.
12. GPT-5.6 Terra is the initial model candidate, subject to the internal acceptance gate.

## 20. Open decisions before implementation planning

These decisions do not change the architecture, but they must be resolved in the implementation plan:

- Exact pilot date and available engineering weeks.
- Expected number of researchers and concurrent jobs.
- Data sensitivity and whether an external LLM API may receive experiment metadata.
- Sentaurus version, supported tools, scheduler, operating system, and remote-network constraints.
- Preferred web stack and identity provider.
- Required report format beyond Markdown and HTML.
- Initial material parameter source approved by the research team.
- Runtime and cost budget per experiment.

## 21. Source baseline

The following sources informed this design and should be pinned in the project source manifest:

- [DEVSIM repository and capabilities](https://github.com/devsim/devsim)
- [DEVSIM Manual 2.11.0](https://devsim.net/)
- [DEVSIM equation and model documentation](https://devsim.net/models.html)
- [DEVSIM command reference](https://devsim.net/CommandReference.html)
- [OpenHands Agent Skills and Context](https://docs.openhands.dev/sdk/guides/skill)
- [OpenHands model recommendations](https://docs.openhands.dev/openhands/usage/llms/llms)
- [OpenAI model catalog and current pricing](https://developers.openai.com/api/docs/models)
- [Synopsys Sentaurus TCAD product overview](https://www.synopsys.com/manufacturing/tcad.html)
- [AgenticTCAD paper](https://arxiv.org/abs/2512.23742)

Model prices, model rankings, simulator versions, and provider capabilities change. Recheck them when freezing the pilot deployment. The architecture must not depend on any particular model name or price.
