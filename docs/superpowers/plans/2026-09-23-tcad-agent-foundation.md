# TCAD Agent Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested local foundation that turns simulator-neutral experiment specifications into validated DEVSIM runs, searchable TCAD knowledge, reproducible bundles, and an OpenHands-ready typed tool surface without hard-coding device types.

**Architecture:** A Python package owns the canonical domain model, capability checks, adapter protocol, validators, knowledge retrieval, and bundle format. DEVSIM is an isolated sibling installation invoked through a narrow runner, while Sentaurus is represented by the same adapter and runner contracts and refuses execution until a licensed remote endpoint is configured. OpenHands uses typed tools and progressively loaded skills; it never writes simulator syntax or bypasses validation.

**Tech Stack:** Python 3.14, DEVSIM 2.9.1, Pydantic 2, Pint, Typer, Jinja2, SQLite FTS5, NumPy, FastEmbed as an optional semantic provider, OpenHands SDK 1.49.4, OpenHands Tools 1.49.4, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-22-tcad-agent-platform-design.md`

## Global Constraints

- `ExperimentSpec` is the stable simulator-neutral contract.
- Devices are compositions of regions, contacts, profiles, models, studies, and observables. Product code must not branch on a device name.
- The first executable slice supports one-dimensional silicon structures, equilibrium electrostatics, and a narrow drift-diffusion DC sweep.
- DEVSIM is the local development backend. Sentaurus remains a remote licensed backend behind the same protocol.
- Unsupported physics, missing consequential inputs, and unsupported backend capabilities must be refused explicitly.
- Every run records the normalized specification, source versions, hashes, logs, results, validation output, and limitations.
- LLM output cannot directly become shell commands or simulator input.
- Proprietary Sentaurus documentation and artifacts must not enter the repository or an external model context.
- Python dependencies and simulator versions are pinned in the lock file and captured in every bundle.
- No remote repository is configured and nothing is pushed until the user supplies the destination.

## Decisions Resolved for This Foundation

- Target one local researcher and one simulation job at a time.
- Treat all experiment metadata as potentially sensitive; external LLM use is optional and disabled without explicit credentials.
- Produce Markdown and JSON reports in this milestone.
- Use reviewed constants from the DEVSIM silicon examples as the initial registry, with source URLs and review status attached to every record.
- Default budgets are 20 agent steps, 3 recovery attempts, 10 simulation points, 10 minutes wall time, and 1 GB output per experiment.
- The Sentaurus version, scheduler, operating system, and endpoint remain deployment configuration because that machine is not available yet.

## Review Focus

- A specification containing unknown keys must fail instead of silently dropping researcher intent.
- Quantities with incompatible or missing units must fail before compilation.
- A requested model absent from the chosen backend manifest must return a typed capability refusal.
- A failed or timed-out simulator process must never be reported as a valid result or leave a successful bundle state.
- Retrieved passages from stale, unreviewed, or backend-incompatible sources must not outrank reviewed version-compatible material.

## Repository Map

```text
TCAD Agent/
  .gitignore
  .python-version
  AGENTS.md
  README.md
  pyproject.toml
  requirements.lock
  apps/cli.py
  src/tcad_agent/
    domain/{models.py,units.py,errors.py}
    capabilities/{models.py,service.py}
    adapters/{base.py,devsim/compiler.py,devsim/manifest.yaml,sentaurus/manifest.yaml}
    runners/{models.py,local.py,remote.py}
    results/models.py
    validation/{models.py,engine.py}
    bundles/{models.py,writer.py}
    reporting/markdown.py
    knowledge/{models.py,ingest.py,retrieve.py}
    agent/{tools.py,runtime.py}
  registries/{materials/silicon.yaml,physics/classical.yaml}
  knowledge-sources/manifests/sources.yaml
  skills/*/SKILL.md
  examples/{pn-junction.yaml,pin-diode.yaml}
  evaluations/{retrieval/questions.yaml,conformance/cases.yaml}
  tests/{unit,integration,e2e}/
  docs/
```

### Task 1: Reproducible repository and DEVSIM installation

**Files:**
- Create: `.gitignore`
- Create: `.python-version`
- Create: `AGENTS.md`
- Create: `README.md`
- Create: `pyproject.toml`
- Create: `requirements.lock`
- Create: `tests/integration/test_devsim_install.py`
- External create: `/Users/satyagni/Documents/NovAtom Labs/devsim/.venv`
- External create: `/Users/satyagni/Documents/NovAtom Labs/devsim/source`

**Interfaces:**
- Consumes: official DEVSIM repository and PyPI package metadata.
- Produces: `/Users/satyagni/Documents/NovAtom Labs/devsim/.venv/bin/python`, project `.venv/bin/python`, and the standard test and lint commands used by every later task.

- [ ] **Step 1: Initialize local version control and write the environment contract**

Run:

```bash
git init -b main
```

Create `.python-version` with `3.14` and a `pyproject.toml` that declares Python `>=3.14,<3.15`, runtime dependencies `pydantic`, `pint`, `typer`, `jinja2`, `PyYAML`, and `numpy`, optional groups for `knowledge` and `agent`, and development dependencies `pytest`, `pytest-cov`, `ruff`, and `mypy`. Pin OpenHands SDK and Tools to the same `1.49.4` version. Then create the project test environment before the first RED run:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip "pip-tools==7.5.2"
.venv/bin/pip-compile --output-file requirements.lock --extra dev --extra knowledge --extra agent pyproject.toml
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install -e . --no-deps
```

- [ ] **Step 2: Write the failing DEVSIM installation test**

```python
from pathlib import Path
import subprocess


DEVSIM_PYTHON = Path("/Users/satyagni/Documents/NovAtom Labs/devsim/.venv/bin/python")


def test_devsim_sibling_install_imports_and_reports_version() -> None:
    assert DEVSIM_PYTHON.is_file()
    completed = subprocess.run(
        [str(DEVSIM_PYTHON), "-c", "import devsim; print('DEVSIM_VERSION=' + devsim.__version__)"],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert "DEVSIM_VERSION=2.9.1" in completed.stdout
```

- [ ] **Step 3: Run the test and verify RED**

Run: `.venv/bin/pytest tests/integration/test_devsim_install.py -q`

Expected: FAIL because the sibling interpreter does not exist.

- [ ] **Step 4: Install the simulator without modifying global Python**

Run:

```bash
mkdir -p "/Users/satyagni/Documents/NovAtom Labs/devsim"
git clone https://github.com/devsim/devsim.git "/Users/satyagni/Documents/NovAtom Labs/devsim/source"
python3 -m venv "/Users/satyagni/Documents/NovAtom Labs/devsim/.venv"
"/Users/satyagni/Documents/NovAtom Labs/devsim/.venv/bin/python" -m pip install --upgrade pip
"/Users/satyagni/Documents/NovAtom Labs/devsim/.venv/bin/python" -m pip install "devsim==2.9.1"
```

Record the DEVSIM source commit in `README.md`. Do not copy the source tree into this repository.

- [ ] **Step 5: Verify GREEN and baseline quality commands**

Run: `.venv/bin/pytest tests/integration/test_devsim_install.py -q`

Expected: PASS.

Run: `.venv/bin/ruff check . && .venv/bin/mypy src`

Expected: both commands exit 0.

- [ ] **Step 6: Commit**

```bash
git add .gitignore .python-version AGENTS.md README.md pyproject.toml requirements.lock tests/integration/test_devsim_install.py
git commit -m "build: initialize tcad agent foundation"
```

### Task 2: Strict, unit-safe simulator-neutral experiment specification

**Files:**
- Create: `src/tcad_agent/domain/errors.py`
- Create: `src/tcad_agent/domain/units.py`
- Create: `src/tcad_agent/domain/models.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/domain/test_experiment_spec.py`
- Create: `examples/pn-junction.yaml`
- Create: `examples/pin-diode.yaml`

**Interfaces:**
- Consumes: no earlier product interfaces.
- Produces: `ExperimentSpec.model_validate(data)`, `ExperimentSpec.normalized() -> dict[str, object]`, `QuantityValue.to(unit: str) -> float`, and immutable typed region, profile, contact, physics, study, and observable objects.

- [ ] **Step 1: Write failing contract tests**

```python
import pytest
from pydantic import ValidationError

from tcad_agent.domain.models import ExperimentSpec


def minimal_spec() -> dict:
    return {
        "schema_version": "1.0",
        "name": "two-region-study",
        "dimension": 1,
        "regions": [
            {"id": "left", "material": "silicon", "x0": "0 um", "x1": "0.5 um"},
            {"id": "right", "material": "silicon", "x0": "0.5 um", "x1": "1 um"},
        ],
        "profiles": [
            {"kind": "constant", "region": "left", "species": "acceptor", "value": "1e17 cm^-3"},
            {"kind": "constant", "region": "right", "species": "donor", "value": "1e16 cm^-3"},
        ],
        "contacts": [
            {"id": "anode", "location": "x_min", "kind": "ohmic"},
            {"id": "cathode", "location": "x_max", "kind": "ohmic"},
        ],
        "physics": {"equations": ["poisson", "electron_continuity", "hole_continuity"]},
        "study": {"kind": "dc", "contact": "anode", "start": "0 V", "stop": "0.2 V", "step": "0.1 V"},
        "observables": ["terminal_current", "potential", "electron_density", "hole_density"],
    }


def test_rejects_unknown_keys() -> None:
    data = minimal_spec() | {"device_type": "pn_diode"}
    with pytest.raises(ValidationError, match="device_type"):
        ExperimentSpec.model_validate(data)


def test_rejects_incompatible_units() -> None:
    data = minimal_spec()
    data["regions"][0]["x1"] = "5 V"
    with pytest.raises(ValidationError, match="length"):
        ExperimentSpec.model_validate(data)


def test_rejects_gaps_between_regions() -> None:
    data = minimal_spec()
    data["regions"][1]["x0"] = "0.6 um"
    with pytest.raises(ValidationError, match="contiguous"):
        ExperimentSpec.model_validate(data)


def test_normalization_is_independent_of_input_units() -> None:
    first = ExperimentSpec.model_validate(minimal_spec()).normalized()
    second_data = minimal_spec()
    second_data["regions"][0]["x1"] = "500 nm"
    second = ExperimentSpec.model_validate(second_data).normalized()
    assert first == second
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv/bin/pytest tests/unit/domain/test_experiment_spec.py -q`

Expected: collection error because `tcad_agent.domain.models` does not exist.

- [ ] **Step 3: Implement strict compositional models**

Use `ConfigDict(extra="forbid", frozen=True)` on every model. Parse quantities with Pint into base SI units, validate dimensions at field boundaries, require ordered contiguous one-dimensional regions, require unique IDs, and verify profile references and study contacts. Do not include a `device_type` field.

The public root must be:

```python
class ExperimentSpec(StrictModel):
    schema_version: Literal["1.0"]
    name: str
    dimension: Literal[1]
    regions: tuple[Region1D, ...]
    profiles: tuple[ConstantProfile, ...]
    contacts: tuple[Contact, ...]
    physics: PhysicsSelection
    study: EquilibriumStudy | DCStudy
    observables: tuple[Observable, ...]
    metadata: dict[str, str] = Field(default_factory=dict)

    def normalized(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude_none=True)
```

- [ ] **Step 4: Verify GREEN and add two ordinary fixtures**

Run: `.venv/bin/pytest tests/unit/domain/test_experiment_spec.py -q`

Expected: 4 passed.

Add PN and PIN YAML fixtures that validate through the same `ExperimentSpec` path. Their names may describe the examples, but no production code may inspect those names.

Add `valid_spec`, `unsupported_spec`, `devsim_manifest`, and `sentaurus_manifest` test fixtures to `tests/conftest.py`; later tasks consume these public test fixtures rather than duplicating setup.

- [ ] **Step 5: Commit**

```bash
git add src/tcad_agent/domain tests/conftest.py tests/unit/domain examples
git commit -m "feat: add simulator-neutral experiment specification"
```

### Task 3: Capability manifests and backend contracts

**Files:**
- Create: `src/tcad_agent/capabilities/models.py`
- Create: `src/tcad_agent/capabilities/service.py`
- Create: `src/tcad_agent/adapters/base.py`
- Create: `src/tcad_agent/adapters/devsim/manifest.yaml`
- Create: `src/tcad_agent/adapters/sentaurus/manifest.yaml`
- Create: `tests/unit/capabilities/test_capabilities.py`

**Interfaces:**
- Consumes: `ExperimentSpec` from Task 2.
- Produces: `CapabilityService.check(spec, manifest) -> CapabilityDecision`, `Adapter.compile(spec, workspace) -> CompiledJob`, and typed `supported`, `needs_input`, `backend_unsupported`, and `platform_unsupported` outcomes.

- [ ] **Step 1: Write failing capability tests**

```python
from tcad_agent.capabilities.models import CapabilityManifest, CapabilityStatus
from tcad_agent.capabilities.service import CapabilityService
from tcad_agent.domain.models import ExperimentSpec


def test_refuses_model_missing_from_backend(valid_spec: ExperimentSpec) -> None:
    requested = valid_spec.model_copy(
        update={"physics": valid_spec.physics.model_copy(update={"models": ("hydrodynamic",)})}
    )
    manifest = CapabilityManifest.model_validate(
        {"backend": "devsim", "dimensions": [1], "equations": ["poisson"], "models": []}
    )
    decision = CapabilityService().check(requested, manifest)
    assert decision.status is CapabilityStatus.BACKEND_UNSUPPORTED
    assert decision.issues[0].path == "physics.models[0]"


def test_same_composition_can_target_two_manifests(valid_spec: ExperimentSpec) -> None:
    service = CapabilityService()
    assert service.check(valid_spec, devsim_manifest()).status is CapabilityStatus.SUPPORTED
    assert service.check(valid_spec, sentaurus_manifest()).status is CapabilityStatus.SUPPORTED
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv/bin/pytest tests/unit/capabilities/test_capabilities.py -q`

Expected: collection error because capability modules do not exist.

- [ ] **Step 3: Implement data-driven decisions and adapter protocol**

```python
class Adapter(Protocol):
    @property
    def manifest(self) -> CapabilityManifest: ...

    def compile(self, spec: ExperimentSpec, workspace: Path) -> CompiledJob: ...

    def normalize(self, native: NativeRunResult) -> CanonicalResult: ...
```

Load manifests from package data. Capability checks compare dimension, equations, profiles, contact kinds, studies, models, and observables. They must not contain name-based or fixture-based conditions. The Sentaurus manifest declares planned portable features but its runner state is `unconfigured`.

- [ ] **Step 4: Verify GREEN**

Run: `.venv/bin/pytest tests/unit/capabilities/test_capabilities.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/tcad_agent/capabilities src/tcad_agent/adapters tests/unit/capabilities
git commit -m "feat: add backend capability contracts"
```

### Task 4: Deterministic DEVSIM compiler, local runner, and canonical results

**Files:**
- Create: `src/tcad_agent/adapters/devsim/compiler.py`
- Create: `src/tcad_agent/adapters/devsim/runtime.py`
- Create: `src/tcad_agent/runners/models.py`
- Create: `src/tcad_agent/runners/local.py`
- Create: `src/tcad_agent/results/models.py`
- Create: `registries/materials/silicon.yaml`
- Create: `registries/physics/classical.yaml`
- Create: `tests/unit/adapters/test_devsim_compiler.py`
- Create: `tests/integration/test_devsim_runner.py`

**Interfaces:**
- Consumes: `ExperimentSpec`, `CapabilityDecision`, and reviewed registry entries.
- Produces: `DevsimAdapter.compile(...) -> CompiledJob`, `LocalRunner.run(job, budget) -> NativeRunResult`, and `DevsimAdapter.normalize(...) -> CanonicalResult`.

- [ ] **Step 1: Write failing deterministic compiler tests**

```python
def test_compiler_is_deterministic_and_name_agnostic(valid_spec, tmp_path) -> None:
    adapter = DevsimAdapter.from_defaults()
    first = adapter.compile(valid_spec, tmp_path / "first")
    renamed = valid_spec.model_copy(update={"name": "arbitrary-research-structure"})
    second = adapter.compile(renamed, tmp_path / "second")
    assert first.runtime_digest == second.runtime_digest
    assert first.input_digest != second.input_digest
    assert first.entrypoint.name == "run_devsim.py"


def test_compiler_rejects_without_writing_files(unsupported_spec, tmp_path) -> None:
    with pytest.raises(CapabilityError):
        DevsimAdapter.from_defaults().compile(unsupported_spec, tmp_path)
    assert not tmp_path.exists()
```

- [ ] **Step 2: Run compiler tests and verify RED**

Run: `.venv/bin/pytest tests/unit/adapters/test_devsim_compiler.py -q`

Expected: collection error because the compiler does not exist.

- [ ] **Step 3: Implement deterministic compilation**

The compiler must serialize a normalized JSON payload and a fixed reviewed Python runtime. The runtime loops over regions and profiles from data, builds a one-dimensional mesh, applies contact locations, creates Poisson and drift-diffusion equations through reviewed helper functions adapted from Apache-2.0 DEVSIM examples, solves equilibrium, walks the requested DC points, and writes `native_result.json`. The compiler generates no equation text from an LLM and uses no fixture names.

`CompiledJob` must contain:

```python
class CompiledJob(StrictModel):
    backend: Literal["devsim", "sentaurus"]
    entrypoint: Path
    arguments: tuple[str, ...]
    environment: dict[str, str]
    input_files: tuple[Path, ...]
    input_digest: str
    runtime_digest: str
    compiler_version: str
```

- [ ] **Step 4: Verify compiler GREEN**

Run: `.venv/bin/pytest tests/unit/adapters/test_devsim_compiler.py -q`

Expected: all tests pass.

- [ ] **Step 5: Write failing real-run integration tests**

```python
@pytest.mark.integration
@pytest.mark.parametrize("fixture_name", ["pn-junction.yaml", "pin-diode.yaml"])
def test_two_structures_run_through_one_backend_path(fixture_name, tmp_path) -> None:
    spec = ExperimentSpec.model_validate(yaml.safe_load((EXAMPLES / fixture_name).read_text()))
    adapter = DevsimAdapter.from_defaults()
    job = adapter.compile(spec, tmp_path / fixture_name.removesuffix(".yaml"))
    native = LocalRunner(devsim_python=DEVSIM_PYTHON).run(job, RunBudget(seconds=120))
    result = adapter.normalize(native)
    assert result.status == "completed"
    assert result.bias_points
    assert all(point.converged for point in result.bias_points)
    assert set(result.terminals) == {"anode", "cathode"}
```

- [ ] **Step 6: Run integration tests and verify RED**

Run: `.venv/bin/pytest tests/integration/test_devsim_runner.py -q -m integration`

Expected: FAIL because runner and normalizer are missing.

- [ ] **Step 7: Implement bounded subprocess execution and normalization**

Use `subprocess.Popen` with an explicit executable, fixed argument list, sanitized environment allowlist, workspace-only current directory, process-group timeout termination, and stdout and stderr files. Never invoke a shell. Treat nonzero exits, missing result files, malformed result JSON, and timeouts as typed failures. Normalize terminal currents, biases, convergence state, and field arrays into SI units.

- [ ] **Step 8: Verify integration GREEN**

Run: `.venv/bin/pytest tests/integration/test_devsim_runner.py -q -m integration`

Expected: 2 passed and both real DEVSIM subprocesses exit 0.

- [ ] **Step 9: Commit**

```bash
git add src/tcad_agent/adapters/devsim src/tcad_agent/runners src/tcad_agent/results registries tests/unit/adapters tests/integration/test_devsim_runner.py
git commit -m "feat: run generic experiments through devsim"
```

### Task 5: Validation, provenance, bundles, and reports

**Files:**
- Create: `src/tcad_agent/validation/models.py`
- Create: `src/tcad_agent/validation/engine.py`
- Create: `src/tcad_agent/bundles/models.py`
- Create: `src/tcad_agent/bundles/writer.py`
- Create: `src/tcad_agent/reporting/markdown.py`
- Create: `tests/unit/validation/test_validation.py`
- Create: `tests/integration/test_bundle.py`

**Interfaces:**
- Consumes: `ExperimentSpec`, `CompiledJob`, `NativeRunResult`, and `CanonicalResult`.
- Produces: `ValidationEngine.validate(...) -> ValidationReport`, `BundleWriter.write(...) -> ExperimentBundle`, and `MarkdownReport.render(...) -> str`.

- [ ] **Step 1: Write failing validation tests**

```python
def test_converged_but_nonconserving_result_fails_physical_validation() -> None:
    result = canonical_result(anode_current=1.0, cathode_current=-0.7, converged=True)
    report = ValidationEngine(current_rtol=1e-6).validate(result)
    assert report.overall == "failed"
    assert report.checks_by_id["terminal-current-conservation"].status == "failed"


def test_failed_process_cannot_be_validated_as_success() -> None:
    result = canonical_result(status="execution_failed", bias_points=())
    report = ValidationEngine().validate(result)
    assert report.overall == "failed"
    assert report.checks_by_id["execution-status"].status == "failed"
```

- [ ] **Step 2: Run validation tests and verify RED**

Run: `.venv/bin/pytest tests/unit/validation/test_validation.py -q`

Expected: collection error because validation modules do not exist.

- [ ] **Step 3: Implement layered deterministic validators**

Implement execution status, per-point convergence, finite numeric values, expected point count, terminal current conservation, nonnegative carrier density, monotonic requested bias, and registry provenance checks. Each check returns ID, level, status, measured value, limit, message, and evidence paths. Overall status is the worst non-waived check.

- [ ] **Step 4: Verify validation GREEN**

Run: `.venv/bin/pytest tests/unit/validation/test_validation.py -q`

Expected: all tests pass.

- [ ] **Step 5: Write failing immutable bundle test**

```python
def test_bundle_manifest_hashes_every_artifact_and_report_uses_structured_values(tmp_path) -> None:
    bundle = BundleWriter(tmp_path).write(bundle_inputs())
    manifest = json.loads((bundle.root / "manifest.json").read_text())
    assert manifest["state"] == "completed"
    assert set(manifest["artifacts"]) >= {
        "experiment.json", "compiled/input.json", "logs/stdout.log",
        "results/canonical.json", "validation/report.json", "report.md"
    }
    assert all(item["sha256"] for item in manifest["artifacts"].values())
    assert "1.000000e+00 A" in (bundle.root / "report.md").read_text()
```

- [ ] **Step 6: Run bundle test and verify RED**

Run: `.venv/bin/pytest tests/integration/test_bundle.py -q`

Expected: FAIL because bundle writer does not exist.

- [ ] **Step 7: Implement atomic bundle finalization and deterministic reporting**

Write into a staging directory, hash every file, write the manifest last, then rename to the final run ID. Use states `preparing`, `running`, `failed`, and `completed`; only `completed` bundles may have a success report. Numeric report tables must come only from `CanonicalResult`, never prose extraction.

- [ ] **Step 8: Verify bundle GREEN and commit**

Run: `.venv/bin/pytest tests/unit/validation tests/integration/test_bundle.py -q`

Expected: all tests pass.

```bash
git add src/tcad_agent/validation src/tcad_agent/bundles src/tcad_agent/reporting tests/unit/validation tests/integration/test_bundle.py
git commit -m "feat: validate and bundle simulation evidence"
```

### Task 6: Versioned hybrid knowledge layer and procedural skills

**Files:**
- Create: `src/tcad_agent/knowledge/models.py`
- Create: `src/tcad_agent/knowledge/ingest.py`
- Create: `src/tcad_agent/knowledge/retrieve.py`
- Create: `knowledge-sources/manifests/sources.yaml`
- Create: `evaluations/retrieval/questions.yaml`
- Create: `skills/{specification,capability-checking,devsim-compilation,solver-recovery,result-validation,source-citation,reporting,sentaurus-boundary}/SKILL.md`
- Create: `tests/unit/knowledge/test_retrieval.py`
- Create: `tests/unit/agent/test_skills.py`

**Interfaces:**
- Consumes: approved local or downloaded source documents plus source manifest metadata.
- Produces: `KnowledgeIndex.build(...)`, `HybridRetriever.search(query, filters, limit) -> tuple[Passage, ...]`, and OpenHands-loadable AgentSkills directories.

- [ ] **Step 1: Write failing retrieval tests**

```python
def test_reviewed_version_compatible_source_outranks_stale_source(tmp_path) -> None:
    index = build_test_index(
        tmp_path,
        passages=[
            passage("old", "DEVSIM contact equation", version="1.0", reviewed=False),
            passage("current", "DEVSIM contact equation", version="2.9", reviewed=True),
        ],
    )
    hits = index.search("contact equation", filters={"backend": "devsim", "version": "2.9"}, limit=2)
    assert [hit.id for hit in hits] == ["current"]
    assert hits[0].citation.source_id


def test_backend_filter_excludes_sentaurus_text(tmp_path) -> None:
    index = build_mixed_backend_index(tmp_path)
    assert all(hit.backend == "devsim" for hit in index.search("mobility model", {"backend": "devsim"}, 5))
```

- [ ] **Step 2: Run retrieval tests and verify RED**

Run: `.venv/bin/pytest tests/unit/knowledge/test_retrieval.py -q`

Expected: collection error because knowledge modules do not exist.

- [ ] **Step 3: Implement manifest-driven ingestion and hybrid ranking**

Chunk by heading and paragraph boundaries, preserve source ID, title, URL, license, trust level, backend, simulator version, document version, review state, and content hash. Store lexical content in SQLite FTS5. Define an `EmbeddingProvider` protocol and a FastEmbed implementation; tests use a deterministic in-memory provider. Combine reciprocal ranks, then apply reviewed, trust, backend, and version gates before returning passages. No source without license and access metadata may be ingested.

- [ ] **Step 4: Verify retrieval GREEN**

Run: `.venv/bin/pytest tests/unit/knowledge/test_retrieval.py -q`

Expected: all tests pass.

- [ ] **Step 5: Create and test eight concise OpenHands skills**

Each `SKILL.md` uses valid AgentSkills frontmatter and gives a bounded procedure, required typed tools, refusal conditions, and evidence requirements. The Sentaurus skill explicitly prohibits inventing syntax and requires version-compatible licensed retrieval.

```python
def test_all_skills_load_through_openhands() -> None:
    from openhands.sdk.skills import load_skills_from_dir

    _, _, skills = load_skills_from_dir(SKILLS_ROOT)
    assert set(skills) == {
        "specification", "capability-checking", "devsim-compilation", "solver-recovery",
        "result-validation", "source-citation", "reporting", "sentaurus-boundary",
    }
```

Run: `.venv/bin/pytest tests/unit/agent/test_skills.py -q`

Expected: PASS after the skill directories exist.

- [ ] **Step 6: Commit**

```bash
git add src/tcad_agent/knowledge knowledge-sources evaluations/retrieval skills tests/unit/knowledge tests/unit/agent/test_skills.py
git commit -m "feat: add versioned tcad retrieval and agent skills"
```

### Task 7: Typed OpenHands tools, CLI workflow, and Sentaurus refusal boundary

**Files:**
- Create: `src/tcad_agent/agent/tools.py`
- Create: `src/tcad_agent/agent/runtime.py`
- Create: `src/tcad_agent/runners/remote.py`
- Create: `apps/cli.py`
- Create: `tests/unit/agent/test_tools.py`
- Create: `tests/e2e/test_cli_workflow.py`

**Interfaces:**
- Consumes: every stable interface from Tasks 2 through 6.
- Produces: typed `validate_spec`, `search_knowledge`, `compile_experiment`, `run_experiment`, `validate_result`, and `build_report` functions; CLI commands `validate`, `compile`, `run`, `report`, and `knowledge search`.

- [ ] **Step 1: Write failing tool safety tests**

```python
def test_run_tool_requires_validated_plan(tmp_path) -> None:
    tools = build_tools(tmp_path)
    response = tools.run_experiment({"spec_path": "spec.yaml", "backend": "devsim"})
    assert response.status == "refused"
    assert response.code == "approval_required"


def test_sentaurus_run_refuses_without_configured_remote() -> None:
    response = build_tools().compile_experiment(valid_spec_payload(), backend="sentaurus")
    assert response.status == "refused"
    assert response.code == "backend_unconfigured"
```

- [ ] **Step 2: Run tool tests and verify RED**

Run: `.venv/bin/pytest tests/unit/agent/test_tools.py -q`

Expected: collection error because agent tools do not exist.

- [ ] **Step 3: Implement typed tools and OpenHands runtime factory**

Tool inputs and outputs are Pydantic models. The runtime factory loads the eight skills, registers only the typed domain tools, reads model name and reasoning effort from environment, and omits a general terminal tool from the production profile. No LLM credential is required to test domain tools.

- [ ] **Step 4: Verify tool GREEN**

Run: `.venv/bin/pytest tests/unit/agent/test_tools.py -q`

Expected: all tests pass.

- [ ] **Step 5: Write failing end-to-end CLI test**

```python
def test_cli_runs_example_to_completed_bundle(tmp_path) -> None:
    result = runner.invoke(
        app,
        ["run", "examples/pn-junction.yaml", "--backend", "devsim", "--approve", "--output", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    manifest = json.loads(next(tmp_path.glob("*/manifest.json")).read_text())
    assert manifest["state"] == "completed"
    assert (next(tmp_path.iterdir()) / "report.md").is_file()
```

- [ ] **Step 6: Run end-to-end test and verify RED**

Run: `.venv/bin/pytest tests/e2e/test_cli_workflow.py -q`

Expected: FAIL because the CLI does not exist.

- [ ] **Step 7: Implement the CLI orchestration**

The CLI performs parse, normalize, capability check, plan creation, compile, bounded run, normalize, validate, bundle, and report in that order. `--approve` is required for execution in interactive use; the test runner may provide an explicit approved plan fixture. Return nonzero on validation, capability, execution, or physical failure and print the bundle location for both success and failure.

- [ ] **Step 8: Verify end-to-end GREEN and commit**

Run: `.venv/bin/pytest tests/e2e/test_cli_workflow.py -q`

Expected: 1 passed with a real DEVSIM execution.

```bash
git add src/tcad_agent/agent src/tcad_agent/runners/remote.py apps tests/unit/agent/test_tools.py tests/e2e
git commit -m "feat: expose approved tcad workflow to openhands and cli"
```

### Task 8: Full verification, documentation, and foundation acceptance

**Files:**
- Modify: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/operations/devsim.md`
- Create: `docs/operations/sentaurus-integration.md`
- Create: `evaluations/conformance/cases.yaml`
- Create: `tests/test_architecture.py`

**Interfaces:**
- Consumes: the finished foundation.
- Produces: a reproducible developer workflow, explicit current limitations, and objective evidence that two structures use one simulator-neutral path.

- [ ] **Step 1: Write failing architecture guard tests**

```python
def test_product_modules_do_not_branch_on_fixture_device_names() -> None:
    forbidden = {"pn_diode", "pin_diode", "moscap", "mosfet"}
    source = "\n".join(path.read_text() for path in SRC_ROOT.rglob("*.py"))
    assert not (forbidden & set(re.findall(r"[a-z_]+", source.lower())))


def test_no_shell_execution_in_runner_sources() -> None:
    source = "\n".join(path.read_text() for path in RUNNERS_ROOT.rglob("*.py"))
    assert "shell=True" not in source
    assert "os.system" not in source
```

- [ ] **Step 2: Run architecture tests and verify RED if a forbidden coupling exists**

Run: `.venv/bin/pytest tests/test_architecture.py -q`

Expected: PASS only after all product modules remain device-name agnostic and shell-free.

- [ ] **Step 3: Document exact operation and limitations**

Document installation, commands, environment variables, bundle anatomy, provenance, adding a new material or backend feature, and the remote Sentaurus protocol required next. State clearly that this foundation is one-dimensional, silicon-first, not calibrated for fabrication, and not yet connected to Sentaurus.

- [ ] **Step 4: Run the complete verification matrix**

Run:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest -q
.venv/bin/pytest tests/integration tests/e2e -q -m integration
.venv/bin/python -m apps.cli validate examples/pn-junction.yaml
.venv/bin/python -m apps.cli validate examples/pin-diode.yaml
```

Expected: every command exits 0, the full suite reports no failures, and both fixtures validate through the same command.

- [ ] **Step 5: Run acceptance demonstrations**

Run each example through the CLI with explicit approval and inspect both manifests. Expected: both are completed, all artifact hashes verify, every mandatory validator passes, and no product module changed between runs.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/architecture.md docs/operations evaluations/conformance tests/test_architecture.py
git commit -m "docs: document and verify tcad agent foundation"
```

## Completion Boundary

This plan completes the local Phase 0 and Phase 1 foundation plus basic validation and bundling. It does not claim pilot readiness. The next approved implementation plan must cover two-dimensional geometry, richer model packs, recovery policies, researcher-facing API and UI, the licensed Sentaurus compiler and remote runner, cross-backend conformance, access control, and the 20-request pilot acceptance campaign.
