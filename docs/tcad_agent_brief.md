# NovAtom TCAD Agent

## Technical Brief

## 1. The idea in one sentence

Build an AI research assistant that turns a semiconductor device research request into a reproducible and validated TCAD simulation, first using DEVSIM and then Sentaurus, without forcing the researcher to write simulator-specific scripts.

## 2. The problem

TCAD is powerful but difficult to use well.

Researchers must translate a scientific objective into geometry, materials, doping, contacts, meshes, physical models, solver settings, sweeps, and post-processing. Much of this work is repetitive, simulator-specific, and difficult to debug.

General-purpose LLMs cannot solve this safely on their own. They often lack detailed TCAD knowledge, confuse simulator syntax, choose incompatible physical models, or produce scripts that look reasonable but are physically wrong.

The opportunity is not to make an LLM pretend to be a simulator. The opportunity is to combine LLM reasoning with structured physics knowledge, deterministic software, real simulators, and automatic validation.

## 3. Product promise

A researcher should be able to say:

> Create a two-dimensional silicon device with these regions, contacts, dimensions, and doping profiles. Run the requested bias study, extract these metrics, and explain whether the result is numerically and physically trustworthy.

The system will then:

1. Understand the request and ask necessary clarification questions.
2. Convert the request into a structured experiment specification.
3. Check units, geometry, model compatibility, and simulator support.
4. Show assumptions and the planned study for researcher approval.
5. Compile the experiment for DEVSIM or Sentaurus.
6. Execute the simulation and recover from bounded numerical failures.
7. Validate convergence and basic physical consistency.
8. Produce plots, metrics, limitations, citations, and a reproducible experiment bundle.

## 4. Composable research platform

The initial evaluations will include a PN diode, MOS capacitor, and planar MOSFET because they test progressively more of the system. They are not separate product modes.

The software will not contain logic such as "if this is a MOSFET, run the MOSFET workflow."

Instead, researchers compose devices from supported primitives:

- Regions and interfaces
- Semiconductor, dielectric, and conductor materials
- Contacts and boundary conditions
- Constant, piecewise, Gaussian, or imported doping profiles
- Meshing and refinement rules
- Physical equations and transport models
- Equilibrium and DC studies
- Bias and parameter sweeps
- Requested fields, curves, and extracted metrics
- Numerical and physical validation checks

This allows researchers to create varied devices within the supported physics envelope without changing product code.

## 5. The central technical decision

The stable center of the product is a simulator-neutral `ExperimentSpec`.

It describes:

- What structure to simulate
- Which materials and parameters to use
- Which physical models to enable
- Which studies to run
- Which outputs to extract
- Which validation checks must pass
- Which resource limits apply

The LLM proposes this specification. Typed software validates it. A backend adapter compiles it for the selected simulator.

```text
Research request
      |
      v
OpenHands agent plus TCAD knowledge
      |
      v
Simulator-neutral ExperimentSpec
      |
      v
Schema, units, physics, and capability checks
      |
      +-------------------+
      |                   |
      v                   v
DEVSIM adapter      Sentaurus adapter
      |                   |
      v                   v
Simulation and normalized results
      |
      v
Validation, report, and reproducible bundle
```

This design prevents the product from becoming tied to DEVSIM. It also makes additional simulators possible later.

## 6. DEVSIM first, Sentaurus before the pilot

### DEVSIM during development

DEVSIM is open-source, Python-scriptable, and supports one-dimensional, two-dimensional, and three-dimensional simulation with user-defined equations. It gives us a fast environment for building the specification, compiler, execution, validation, and reporting layers.

### Sentaurus for the pilot

Sentaurus is the commercial target. It runs on the separate licensed machine.

The main platform will submit signed job bundles to a narrow remote runner. The runner will execute only approved Sentaurus commands, return allowlisted results, and expose the installed simulator capabilities. It will not expose a remote shell to the LLM.

The same portable `ExperimentSpec` must run through both backends. Backend-specific features are allowed only as clearly marked extensions. A result being portable never means that both simulators must produce identical numbers. It means their setup is semantically equivalent and differences remain within expert-approved tolerances.

## 7. How we give the LLM TCAD knowledge

RAG alone is not sufficient. The system needs four knowledge layers.

### 1. Structured registries

Exact facts belong in version-controlled data, not prompts:

- Material parameters and units
- Supported physics models
- Model compatibility rules
- Simulator capabilities
- Validation thresholds
- Parameter provenance

### 2. Retrieval-augmented generation

The retrieval system searches version-matched, authoritative material:

- DEVSIM manuals and command documentation
- Official DEVSIM examples and golden results
- Approved internal NovAtom research notes
- Legally usable papers or textbooks
- Sentaurus documentation within the licensed environment

Every retrieved source carries version, trust level, access scope, checksum, and citation metadata.

### 3. OpenHands skill files

Small procedural skills teach the agent how to work:

- Clarify an incomplete TCAD request
- Plan an experiment
- Design a mesh
- Configure drift-diffusion physics
- Perform bias continuation
- Diagnose convergence failures
- Validate results
- Write the technical report
- Use the DEVSIM or Sentaurus adapter

Skills contain procedures and stop conditions. They do not contain large copied manuals.

### 4. Simulator and validator evidence

The final authority is the executed simulation and deterministic validation, not an LLM answer.

## 8. Four-day knowledge bootstrap

The first useful knowledge layer can be built in three to four focused days.

### Day 1

- Collect and version authoritative DEVSIM documentation and examples.
- Create a source manifest with licensing and provenance.
- Select the initial internal TCAD notes.

### Day 2

- Build hybrid keyword and semantic retrieval.
- Add metadata filters for simulator, version, command, material, model, and trust level.
- Create the first silicon material and physics compatibility registries.

### Day 3

- Create the first eight to ten TCAD skill files.
- Add required evidence, stop conditions, and permitted tool calls to every skill.

### Day 4

- Build a small expert-approved retrieval evaluation set.
- Measure whether the correct sources are found and cited.
- Fix retrieval and chunking before adding more documents.

The goal of this sprint is not complete TCAD knowledge. It is a measured and trustworthy knowledge foundation that can grow.

## 9. Initial scope

The first version should be broad enough for useful research but bounded enough to validate properly.

### Supported initially

- One-dimensional and two-dimensional structures
- Silicon-first material support
- Semiconductor, dielectric, and conductor regions
- Common doping profiles
- Ohmic and idealized gate contacts
- Electrostatics and classical drift-diffusion
- A reviewed set of mobility and recombination models
- Equilibrium and DC bias studies
- Parameter sweeps with strict budgets
- Terminal current, charge, potential, field, and carrier outputs
- Common derived metrics

### Not promised initially

- Production process simulation
- Complex three-dimensional devices
- Quantum transport or Monte Carlo simulation
- Unreviewed GaN, SiC, trap, polarization, or tunneling models
- Full electrothermal or optical coupling
- Automatic fabrication-ready calibration
- Arbitrary LLM-generated simulator code

New capabilities are added through reviewed material packs, physics packs, compiler support, and validation tests. They are not added by changing the prompt.

## 10. Scientific trust and validation

A simulation is not accepted merely because the solver converged.

The system applies four levels of validation:

1. **Specification:** units, geometry, contacts, required parameters, and capability compatibility.
2. **Execution:** completed study points, valid outputs, no NaNs, and successful solver status.
3. **Numerical:** residuals, current conservation, sweep continuity, and mesh sensitivity.
4. **Physical:** expected signs, trends, ranges, equilibrium behavior, and comparison with references when available.

Each check returns `PASS`, `WARN`, `FAIL`, or `NOT_APPLICABLE` with evidence.

Every result records:

- Original request
- Final experiment specification
- Assumptions and sources
- Simulator and adapter versions
- Generated input files
- Solver logs
- Recovery actions
- Validation results
- Plots and extracted data
- File hashes and reproduction instructions

This audit trail is a core differentiator from a generic chatbot that writes scripts.

## 11. Safe failure recovery

The agent may choose only from approved recovery actions, such as:

- Reducing a bias step
- Adding continuation points
- Restarting from the last converged state
- Increasing iteration limits within a cap
- Using an approved damping setting
- Refining the mesh using a declared rule
- Re-running equilibrium initialization

Every recovery attempt is recorded and limited. If the approved repair budget is exhausted, the system stops and explains the failure rather than continuing an expensive loop.

## 12. LLM recommendation

Use **GPT-5.6 Terra** as the first single production model candidate.

- Normal planning and tool use: medium reasoning
- Difficult failure diagnosis and final review: high reasoning
- Current standard API price: $2 per million input tokens and $12 per million output tokens
- OpenHands connection: `openai/gpt-5.6-terra` through its LiteLLM model interface

Why Terra:

- Strong reasoning and agentic tool use
- Structured output and long-context support
- Lower cost than GPT-5.6 Sol, GPT-5.5, Claude Opus 4.8, or GPT-6 Astra
- Model-independent architecture lets us replace it later

Before freezing the pilot, Terra must pass an internal set of 30 to 50 representative TCAD tasks. The test will measure valid tool calls, specification quality, source selection, refusal of unsupported work, end-to-end completion, cost, and latency.

If Terra does not pass, use **GPT-5.5** as the conservative fallback because it has published OpenHands benchmark evidence, despite its higher price.

Cost controls include progressive skill loading, small retrieved passages, prompt caching, compact log summaries, strict tool budgets, and limited recovery attempts.

## 13. Pilot demonstration

The pilot should demonstrate both range and trust.

### Internal conformance cases

- PN junction equilibrium and DC sweep
- MOS capacitor electrostatic and C-V study
- Two-dimensional planar MOSFET transfer and output studies

### Researcher-facing demonstration

The researcher supplies a new in-scope structure and study in natural language. The platform:

1. Clarifies missing scientific choices.
2. Generates and displays the structured plan.
3. Runs it on Sentaurus.
4. Detects and handles a controlled numerical difficulty.
5. Produces validated results and a reproducible report.

This proves that the product is not replaying a memorized example.

## 14. Pilot success criteria

The pilot is ready when:

- At least 20 varied, supported requests complete end to end.
- A researcher can define a new in-scope device without a code change.
- At least 90 percent of supported requests produce a valid specification after clarification.
- Unsupported physics is refused reliably.
- Every reported number traces to simulator output.
- Every scientific claim has computed evidence or a citation.
- Both DEVSIM and Sentaurus pass the cross-backend conformance suite.
- Every run creates a reproducible experiment bundle.
- The main Sentaurus demonstration completes without hidden manual intervention.

## 15. Build sequence

### Phase 0: Knowledge sprint

Build the four-day knowledge foundation, first skills, source registry, and retrieval evaluation.

### Phase 1: End-to-end DEVSIM path

Build the experiment schema, capability checks, DEVSIM compiler, runner, normalized results, and basic report.

### Phase 2: Validation and recovery

Add layered validation, failure classification, approved recovery actions, mesh checks, and audit bundles.

### Phase 3: Researcher experience

Add request clarification, plan approval, progress, reports, plots, and artifact access.

### Phase 4: Sentaurus

Build the licensed remote runner, Sentaurus adapter, controlled Sentaurus knowledge access, and cross-backend conformance tests.

### Phase 5: Pilot hardening

Freeze the model and prompts, run the complete evaluation set, add cost monitoring, review security, and prepare the pilot runbook.

## 16. Main risks

| Risk | Response |
|---|---|
| Plausible but wrong physics | Structured registries, validators, citations, and expert review |
| Three hard-coded demos instead of a platform | Composition-based specification and varied evaluation fixtures |
| RAG returns stale documentation | Simulator-version filters, trust levels, and immutable index versions |
| DEVSIM and Sentaurus disagree | Semantic mapping review and expert-approved tolerances |
| Agent loops become expensive | Compact context, caching, budgets, and recovery limits |
| Sentaurus licensing or IP exposure | Licensed remote runner and access-controlled knowledge store |
| Scope expands too early | Published capability envelope and explicit refusal behavior |
| A converged result is still wrong | Multi-level numerical and physical validation |

## 17. What makes this defensible

The defensible asset is not a prompt or a thin wrapper around OpenHands.

It is the accumulated system of:

- Simulator-neutral experiment specifications
- Backend compilers and capability mappings
- Reviewed material and physics registries
- TCAD skill library
- Versioned authoritative knowledge base
- Recovery policies
- Scientific validators
- Cross-simulator benchmarks
- Reproducible experiment history
- Expert-reviewed failure and correction data

This improves with every reviewed experiment and becomes difficult to reproduce without both software and domain expertise.
