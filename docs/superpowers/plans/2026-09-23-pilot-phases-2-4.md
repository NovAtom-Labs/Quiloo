# Pilot Phases 2-4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a tested local researcher web application, bounded validation and recovery, and a simulator-neutral Sentaurus integration boundary without coupling product behavior to any named device.

**Architecture:** A persistent control service owns request state, approvals, event history, and artifact references. The model proposes structured intent through a provider-neutral gateway. Deterministic domain services validate, compile, run, normalize, recover, and report. DEVSIM remains the executable local backend. Sentaurus support is a deterministic compiler, signed remote protocol, and conformance harness until the licensed machine is connected.

**Tech Stack:** Python 3.13, Pydantic 2, OpenHands SDK, LiteLLM through OpenHands, FastAPI, Uvicorn, Jinja2, NumPy, SQLite, Ed25519 signatures from `cryptography`, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-22-tcad-agent-platform-design.md`

## Fixed constraints

- The pilot uses one active model, `bedrock/global.anthropic.claude-sonnet-5`, behind a provider-neutral interface.
- The LLM never writes native simulator syntax or arbitrary shell commands.
- `ExperimentSpec` is the only input accepted by compilers.
- Device names never select code paths. Behavior is derived from regions, contacts, physics, studies, and observables.
- DEVSIM runs locally. Sentaurus runs only on a licensed machine through the narrow remote protocol.
- The local web server binds to `127.0.0.1` by default.
- Deterministic validation is authoritative. Model prose cannot override a failed check.
- Credentials stay in ignored environment files or short-lived deployment identity. No credential appears in source, logs, bundles, or browser responses.
- Every state transition, recovery action, and artifact is auditable.

## Review focus

The implementation must explicitly cover these input classes and failure modes:

1. Incomplete geometry and ambiguous metal-semiconductor contact semantics must cause clarification before compilation.
2. Invalid or expired Bedrock credentials must produce a safe configuration error without exposing the credential.
3. Duplicate approval and concurrent run requests must be idempotent and must create at most one run.
4. Malformed simulator output, non-finite values, non-convergence, and current imbalance must be classified separately.
5. Sentaurus result bundles with an invalid signature, artifact hash mismatch, unexpected simulator version, or path escape must be rejected.

## Completion boundary

Phases 2 and 3 can meet their full exit conditions on this machine. Phase 4 can deliver and verify the compiler, protocol, signature checks, reference runner service, and cross-backend comparison logic locally. The final Phase 4 exit condition, running the same specification in real Sentaurus, remains conditional on access to the licensed machine, its exact Sentaurus version, and authorized documentation.

## Task 1: Correct and extend the simulator-neutral scientific schema

**Files:**

- Modify: `src/tcad_agent/domain/models.py`
- Modify: `src/tcad_agent/adapters/devsim/compiler.py`
- Modify: `src/tcad_agent/adapters/devsim/manifest.yaml`
- Modify: `src/tcad_agent/adapters/sentaurus/manifest.yaml`
- Test: `tests/unit/domain/test_experiment_spec.py`
- Test: `tests/unit/adapters/test_devsim_compiler.py`

**Interfaces:**

- Add `ContactKind.METAL_WORK_FUNCTION`.
- Require `work_function` to have energy units and use eV in serialized examples.
- Reject missing work function for a metal-work-function contact and reject it for an ohmic contact.
- Extend `Observable` with charge density, conduction band, valence band, Fermi level, electron current density, hole current density, electron mobility, hole mobility, and recombination rate.
- Keep backend support controlled only by each `CapabilityManifest`.

- [ ] Write failing tests that establish energy dimensionality and conditional contact fields:

```python
def test_metal_contact_requires_energy_work_function() -> None:
    contact = Contact.model_validate({
        "id": "anode",
        "location": "x_min",
        "kind": "metal_work_function",
        "work_function": "4.10 eV",
    })
    assert contact.work_function is not None
    assert contact.work_function.to("eV") == pytest.approx(4.10)


def test_ohmic_contact_rejects_work_function() -> None:
    with pytest.raises(ValidationError, match="ohmic contact"):
        Contact.model_validate({
            "id": "anode",
            "location": "x_min",
            "kind": "ohmic",
            "work_function": "4.10 eV",
        })
```

- [ ] Run `pytest tests/unit/domain/test_experiment_spec.py -q` and confirm it fails because the kind and energy units are unsupported.
- [ ] Implement the tagged contact constraints and observable enum additions. Make the DEVSIM manifest reject unsupported metal-contact semantics instead of approximating them.
- [ ] Add a regression test proving the current DEVSIM examples still compile and a requested unsupported observable produces a capability refusal.
- [ ] Run `pytest tests/unit/domain/test_experiment_spec.py tests/unit/adapters/test_devsim_compiler.py -q` and confirm it passes.
- [ ] Commit with `git add src/tcad_agent/domain src/tcad_agent/adapters tests/unit/domain tests/unit/adapters && git commit -m "feat: extend portable scientific schema"`.

## Task 2: Add failure taxonomy and bounded recovery policy

**Files:**

- Create: `src/tcad_agent/recovery/__init__.py`
- Create: `src/tcad_agent/recovery/models.py`
- Create: `src/tcad_agent/recovery/policy.py`
- Modify: `src/tcad_agent/validation/models.py`
- Modify: `src/tcad_agent/validation/engine.py`
- Test: `tests/unit/recovery/test_policy.py`
- Test: `tests/unit/validation/test_validation.py`

**Interfaces:**

```python
class FailureKind(StrEnum):
    EXECUTION = "execution"
    TIMEOUT = "timeout"
    NON_CONVERGENCE = "non_convergence"
    MALFORMED_OUTPUT = "malformed_output"
    NONFINITE_RESULT = "nonfinite_result"
    CONSERVATION = "conservation"
    PHYSICAL_SANITY = "physical_sanity"

class RecoveryAction(StrEnum):
    REDUCE_BIAS_STEP = "reduce_bias_step"
    INCREASE_ITERATION_LIMIT = "increase_iteration_limit"
    REFINE_MESH = "refine_mesh"
    STOP_AND_REPORT = "stop_and_report"

class RecoveryPolicy:
    def decide(self, failure: FailureRecord, history: tuple[RecoveryAttempt, ...], budget: RecoveryBudget) -> RecoveryDecision: ...
```

- [ ] Write failing table-driven tests for execution failure, timeout, non-convergence, malformed output, non-finite output, conservation failure, and exhausted budget.

```python
@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (FailureKind.NON_CONVERGENCE, RecoveryAction.REDUCE_BIAS_STEP),
        (FailureKind.NONFINITE_RESULT, RecoveryAction.STOP_AND_REPORT),
        (FailureKind.MALFORMED_OUTPUT, RecoveryAction.STOP_AND_REPORT),
    ],
)
def test_policy_selects_only_allowlisted_actions(kind, expected) -> None:
    decision = RecoveryPolicy().decide(
        FailureRecord(kind=kind, evidence="injected"), (), RecoveryBudget(max_attempts=2)
    )
    assert decision.action is expected
```

- [ ] Run `pytest tests/unit/recovery tests/unit/validation/test_validation.py -q` and confirm the new tests fail because the recovery package does not exist.
- [ ] Implement immutable recovery models, an explicit transition table, attempt accounting, and `NOT_APPLICABLE` validation status.
- [ ] Make `ValidationEngine` expose a deterministic `classify_failures()` result. Never infer failure type from model text.
- [ ] Add tests proving the policy never repeats the same action beyond its limit and always stops when the budget is exhausted.
- [ ] Run the targeted tests and confirm they pass.
- [ ] Commit with `git add src/tcad_agent/recovery src/tcad_agent/validation tests/unit/recovery tests/unit/validation && git commit -m "feat: add bounded validation recovery"`.

## Task 3: Add mesh comparison, event ledger, and complete experiment bundles

**Files:**

- Create: `src/tcad_agent/validation/mesh.py`
- Create: `src/tcad_agent/events/__init__.py`
- Create: `src/tcad_agent/events/models.py`
- Create: `src/tcad_agent/events/ledger.py`
- Modify: `src/tcad_agent/bundles/models.py`
- Modify: `src/tcad_agent/bundles/writer.py`
- Test: `tests/unit/validation/test_mesh.py`
- Test: `tests/unit/events/test_ledger.py`
- Modify: `tests/integration/test_bundle.py`

**Interfaces:**

```python
class MeshComparison(StrictModel):
    field: str
    relative_linf: float
    tolerance: float
    stable: bool

def compare_mesh_results(coarse: FieldSeries, refined: FieldSeries, tolerance: float) -> MeshComparison: ...

class RunEvent(StrictModel):
    sequence: int
    occurred_at: datetime
    kind: RunEventKind
    payload: dict[str, JsonValue]
    previous_hash: str | None
    event_hash: str
```

- [ ] Write failing tests for interpolation onto shared coordinates, stable and unstable refinement, non-overlapping domains, append-only sequence numbers, hash chaining, and mutation detection.
- [ ] Run `pytest tests/unit/validation/test_mesh.py tests/unit/events/test_ledger.py tests/integration/test_bundle.py -q` and confirm failures.
- [ ] Implement NumPy-based one-dimensional interpolation and relative `L-infinity` comparison with an absolute floor near zero.
- [ ] Implement a JSONL ledger that computes each event hash over canonical JSON plus the previous hash and uses `fsync` before acknowledging append.
- [ ] Add `events.jsonl` to `BundleInputs`, copy it into the bundle, and include its digest in the manifest.
- [ ] Add a bundle integration test that verifies every manifest digest and every event-chain link.
- [ ] Run the targeted tests and confirm they pass.
- [ ] Commit with `git add src/tcad_agent/validation src/tcad_agent/events src/tcad_agent/bundles tests/unit tests/integration/test_bundle.py && git commit -m "feat: add mesh validation and audit ledger"`.

## Task 4: Add provider-neutral model gateway and persistent request lifecycle

**Files:**

- Create: `src/tcad_agent/model_gateway/__init__.py`
- Create: `src/tcad_agent/model_gateway/base.py`
- Create: `src/tcad_agent/model_gateway/openhands.py`
- Create: `src/tcad_agent/control/__init__.py`
- Create: `src/tcad_agent/control/models.py`
- Create: `src/tcad_agent/control/store.py`
- Test: `tests/unit/model_gateway/test_openhands.py`
- Test: `tests/unit/control/test_store.py`

**Interfaces:**

```python
class ModelGateway(Protocol):
    def propose(self, request: ResearchRequest, context: AgentContextPacket) -> AgentProposal: ...

class RequestState(StrEnum):
    REQUESTED = "requested"
    NEEDS_CLARIFICATION = "needs_clarification"
    SPEC_DRAFTED = "spec_drafted"
    SPEC_VALIDATED = "spec_validated"
    USER_CONFIRMATION_REQUIRED = "user_confirmation_required"
    COMPILED = "compiled"
    RUNNING = "running"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"

class RequestStore(Protocol):
    def create(self, request: ResearchRequest) -> RequestRecord: ...
    def transition(self, request_id: UUID, expected_revision: int, target: RequestState, data: dict[str, JsonValue]) -> RequestRecord: ...
```

- [ ] Write failing tests with a scripted fake gateway and a temporary SQLite database. Cover valid transitions, illegal skipped states, optimistic concurrency, restart persistence, and secret redaction.

```python
def test_transition_rejects_stale_revision(store: SqliteRequestStore) -> None:
    record = store.create(ResearchRequest(prompt="simulate a junction"))
    store.transition(record.id, record.revision, RequestState.NEEDS_CLARIFICATION, {})
    with pytest.raises(ConcurrentTransitionError):
        store.transition(record.id, record.revision, RequestState.SPEC_DRAFTED, {})
```

- [ ] Run `pytest tests/unit/model_gateway tests/unit/control -q` and confirm import failures.
- [ ] Implement the protocols, immutable proposal schema, legal state transition map, SQLite store, and environment-only OpenHands Bedrock configuration.
- [ ] Map provider authentication failures to `ModelConfigurationError` while discarding request headers and credential text.
- [ ] Add an opt-in `live_bedrock` pytest marker. The default suite must use the fake and make no network request.
- [ ] Run the targeted tests and confirm they pass.
- [ ] Commit with `git add src/tcad_agent/model_gateway src/tcad_agent/control tests/unit/model_gateway tests/unit/control pyproject.toml && git commit -m "feat: add model gateway and request lifecycle"`.

## Task 5: Build the orchestration service and clarification gate

**Files:**

- Create: `src/tcad_agent/control/service.py`
- Create: `src/tcad_agent/control/clarification.py`
- Create: `src/tcad_agent/control/execution.py`
- Modify: `src/tcad_agent/agent/tools.py`
- Test: `tests/unit/control/test_service.py`
- Test: `tests/integration/test_control_workflow.py`

**Interfaces:**

```python
class ControlService:
    def submit(self, prompt: str) -> RequestView: ...
    def answer(self, request_id: UUID, answers: tuple[ClarificationAnswer, ...]) -> RequestView: ...
    def approve(self, request_id: UUID, plan_digest: str) -> RequestView: ...
    def execute(self, request_id: UUID) -> RequestView: ...
```

- [ ] Write a failing integration test that submits `examples/prompts/al-pn-al-equilibrium.md` and asserts that the service asks for both region thicknesses and metal-contact treatment before creating a spec.
- [ ] Write failing tests that prove approval requires the exact plan digest, duplicate approval is idempotent, execution before approval is refused, and two concurrent execute calls create one run.
- [ ] Run `pytest tests/unit/control/test_service.py tests/integration/test_control_workflow.py -q` and confirm failures.
- [ ] Implement a deterministic clarification gate for schema-required facts, then call the model only for intent extraction and phrasing. Feed retrieval citations and capability data as a bounded context packet.
- [ ] After clarification, validate the proposal as `ExperimentSpec`, run capability checks, persist a reviewable plan, and require approval of its digest.
- [ ] Execute through the adapter, runner, normalizer, validation engine, recovery policy, bundle writer, and report builder. The service must record every stage in the ledger.
- [ ] Add tests for unsupported physics, missing knowledge index, DEVSIM execution failure, validation failure, and successful completion.
- [ ] Run the targeted tests and confirm they pass.
- [ ] Commit with `git add src/tcad_agent/control src/tcad_agent/agent/tools.py tests/unit/control tests/integration/test_control_workflow.py && git commit -m "feat: orchestrate approved research workflows"`.

## Task 6: Deliver the loopback web application and executable launcher

**Files:**

- Modify: `pyproject.toml`
- Regenerate: `requirements.lock`
- Create: `src/tcad_agent/web/__init__.py`
- Create: `src/tcad_agent/web/app.py`
- Create: `src/tcad_agent/web/schemas.py`
- Create: `src/tcad_agent/web/templates/index.html`
- Create: `src/tcad_agent/web/static/app.js`
- Create: `src/tcad_agent/web/static/styles.css`
- Create: `src/tcad_agent/web/launcher.py`
- Create: `launch_tcad_agent.command`
- Test: `tests/unit/web/test_api.py`
- Test: `tests/e2e/test_web_workflow.py`

**Interfaces:**

- `GET /` renders the researcher workspace.
- `POST /api/requests` creates a request.
- `GET /api/requests/{id}` returns current state, plan, validation summary, and safe errors.
- `POST /api/requests/{id}/answers` records clarification answers.
- `POST /api/requests/{id}/approve` approves an exact plan digest.
- `POST /api/requests/{id}/run` starts the approved run idempotently.
- `GET /api/requests/{id}/events` streams stage-level server-sent events.
- `GET /api/requests/{id}/artifacts/{name}` downloads an allowlisted artifact from the bundle.

- [ ] Add FastAPI and Uvicorn as explicit runtime dependencies, plus `httpx` to development dependencies.
- [ ] Write failing API tests for every route, path traversal, invalid UUIDs, duplicate run, response secret redaction, and loopback default configuration.

```python
def test_create_request_enters_clarification(client: TestClient) -> None:
    response = client.post("/api/requests", json={"prompt": EQUILIBRIUM_PROMPT})
    assert response.status_code == 201
    assert response.json()["state"] == "needs_clarification"
    assert {q["field"] for q in response.json()["questions"]} >= {
        "geometry.p_region_thickness",
        "geometry.n_region_thickness",
        "contacts.treatment",
    }
```

- [ ] Run `pytest tests/unit/web tests/e2e/test_web_workflow.py -q` and confirm failures.
- [ ] Implement the API and a single-page progressive UI with prompt entry, clarification form, plan review, approval, stage progress, validation table, report preview, and artifact download. Do not expose chain-of-thought.
- [ ] Implement `tcad-agent-web` and `launch_tcad_agent.command`. The launcher starts one loopback server, waits for `/health`, opens the browser, and reuses an already healthy instance.
- [ ] Start the app on an ephemeral port in the end-to-end test and complete a fake-model plus DEVSIM workflow through HTTP.
- [ ] Run the targeted tests and confirm they pass.
- [ ] Commit with `git add pyproject.toml requirements.lock src/tcad_agent/web launch_tcad_agent.command tests/unit/web tests/e2e/test_web_workflow.py && git commit -m "feat: add local researcher web app"`.

## Task 7: Implement the deterministic Sentaurus compiler

**Files:**

- Create: `src/tcad_agent/adapters/sentaurus/compiler.py`
- Create: `src/tcad_agent/adapters/sentaurus/runtime.py`
- Modify: `src/tcad_agent/adapters/sentaurus/__init__.py`
- Modify: `src/tcad_agent/adapters/sentaurus/manifest.yaml`
- Create: `src/tcad_agent/adapters/sentaurus/templates/sdevice.cmd.j2`
- Create: `tests/fixtures/sentaurus/equilibrium_1d/expected_sdevice.cmd`
- Test: `tests/unit/adapters/test_sentaurus_compiler.py`

**Interfaces:**

- Accept only capability-approved one-dimensional silicon drift-diffusion specs.
- Generate a deterministic `sdevice.cmd`, structured job manifest, expected output allowlist, and input digests.
- Map Fermi statistics, mobility, SRH, Auger, and band-gap narrowing through reviewed registry identifiers.
- Never accept raw Sentaurus statements from the request, model, extensions, or environment.

- [ ] Write failing snapshot tests for a portable equilibrium junction, deterministic repeat compilation, unsafe identifier rejection, unsupported model refusal, unsupported observable refusal, and metal work-function contact mapping.
- [ ] Run `pytest tests/unit/adapters/test_sentaurus_compiler.py -q` and confirm failure because no compiler exists.
- [ ] Implement strict renderer input models and Jinja rendering with fixed templates. Hash the normalized specification, compiler version, and generated inputs.
- [ ] Add a syntax-lint pass that rejects undeclared placeholders, newlines in identifiers, absolute paths, shell metacharacters, and unknown model names.
- [ ] Compare generated output byte-for-byte with the reviewed fixture.
- [ ] Run the targeted tests and confirm they pass.
- [ ] Commit with `git add src/tcad_agent/adapters/sentaurus tests/fixtures/sentaurus tests/unit/adapters/test_sentaurus_compiler.py && git commit -m "feat: add deterministic sentaurus compiler"`.

## Task 8: Implement the signed remote runner protocol and reference service

**Files:**

- Modify: `pyproject.toml`
- Regenerate: `requirements.lock`
- Create: `src/tcad_agent/remote_protocol/__init__.py`
- Create: `src/tcad_agent/remote_protocol/models.py`
- Create: `src/tcad_agent/remote_protocol/signing.py`
- Modify: `src/tcad_agent/runners/remote.py`
- Create: `src/tcad_agent/sentaurus_runner/__init__.py`
- Create: `src/tcad_agent/sentaurus_runner/app.py`
- Create: `src/tcad_agent/sentaurus_runner/executor.py`
- Test: `tests/unit/remote_protocol/test_signing.py`
- Test: `tests/unit/runners/test_remote.py`
- Test: `tests/unit/sentaurus_runner/test_service.py`

**Interfaces:**

```python
class SubmitJobRequest(StrictModel):
    protocol_version: Literal["1.0"]
    job_id: UUID
    backend: Literal["sentaurus"]
    required_simulator_version: str
    manifest_sha256: str
    bundle_b64: str
    signature_b64: str

class RemoteSentaurusRunner:
    def submit(self, job: CompiledJob, budget: RunBudget) -> RemoteJobHandle: ...
    def status(self, handle: RemoteJobHandle) -> RemoteJobStatus: ...
    def result(self, handle: RemoteJobHandle) -> NativeRunResult: ...
```

- [ ] Add `cryptography` and `httpx` as explicit dependencies.
- [ ] Write failing tests for valid Ed25519 verification, altered bytes, untrusted key, hash mismatch, wrong backend, version mismatch, expired request, replayed job ID, path traversal, oversized upload, and non-allowlisted output.
- [ ] Run the three targeted test modules and confirm failures.
- [ ] Implement canonical manifest signing and verification. The private signing key is client-side deployment configuration. The runner contains only the trusted public key.
- [ ] Implement the HTTP client with bounded timeouts, explicit status parsing, exact version verification, and no credential or bundle body logging.
- [ ] Implement the reference runner service with isolated per-job directories, archive path validation, resource limits, an exact executable allowlist, and structured status. The Sentaurus executable path comes only from licensed-machine configuration.
- [ ] Keep real execution disabled unless `SENTAURUS_EXECUTABLE`, the exact version, trusted public key, and authorized output allowlist are all configured.
- [ ] Run the targeted tests and confirm they pass.
- [ ] Commit with `git add pyproject.toml requirements.lock src/tcad_agent/remote_protocol src/tcad_agent/runners/remote.py src/tcad_agent/sentaurus_runner tests/unit/remote_protocol tests/unit/runners tests/unit/sentaurus_runner && git commit -m "feat: add signed sentaurus runner protocol"`.

## Task 9: Normalize Sentaurus results and add cross-backend conformance

**Files:**

- Create: `src/tcad_agent/adapters/sentaurus/normalizer.py`
- Create: `src/tcad_agent/conformance/__init__.py`
- Create: `src/tcad_agent/conformance/models.py`
- Create: `src/tcad_agent/conformance/compare.py`
- Modify: `evaluations/conformance/cases.yaml`
- Create: `tests/fixtures/sentaurus/results/equilibrium_1d.json`
- Test: `tests/unit/adapters/test_sentaurus_normalizer.py`
- Test: `tests/unit/conformance/test_compare.py`
- Test: `tests/integration/test_cross_backend_conformance.py`

**Interfaces:**

- Normalize allowlisted scalar tables and one-dimensional fields into `CanonicalResult` with SI units.
- Compare qualitative direction, current conservation, built-in potential, field extrema, carrier profiles, and mesh stability using per-case tolerances.
- Mark each comparison as passed, warning, failed, or not applicable.

- [ ] Write failing tests for valid normalization, missing columns, duplicate coordinates, non-monotonic positions, unit conversion, non-finite values, and exact simulator version capture.
- [ ] Write failing conformance tests proving values within tolerance pass, sign reversal fails, missing required fields fail, and explicitly unsupported comparisons are not applicable.
- [ ] Run the targeted tests and confirm failures.
- [ ] Implement strict tabular parsing and canonical result construction without model involvement.
- [ ] Implement comparison rules from `evaluations/conformance/cases.yaml`, with no universal hard-coded tolerance.
- [ ] Add a `sentaurus` pytest marker. The licensed integration test skips unless endpoint, trusted key, and exact version are configured. A skip is not counted as Phase 4 exit-condition success.
- [ ] Run the targeted tests and confirm fixture-based tests pass and licensed tests report a clear skip on this machine.
- [ ] Commit with `git add src/tcad_agent/adapters/sentaurus src/tcad_agent/conformance evaluations/conformance tests && git commit -m "feat: add sentaurus normalization and conformance"`.

## Task 10: Integrated acceptance, documentation, and licensed-machine handoff

**Files:**

- Modify: `README.md`
- Modify: `docs/operations/devsim.md`
- Modify: `docs/operations/sentaurus-integration.md`
- Create: `docs/operations/local-web-app.md`
- Create: `docs/testing/pilot-acceptance.md`
- Create: `tests/e2e/test_pilot_acceptance.py`
- Modify: `.env.example`

- [ ] Write an end-to-end acceptance test using the scripted model that submits the Al / p-Si / n-Si / Al request, answers clarifications, reviews and approves the plan, runs DEVSIM where its declared capabilities permit, validates results, and downloads a reproducible bundle.
- [ ] Add an acceptance test proving the same approved portable spec compiles for Sentaurus without changing the request or UI state.
- [ ] Add a safe live Bedrock smoke test that runs only with `--run-live-bedrock` and reports authentication failure without printing the key.
- [ ] Run the end-to-end tests first and fix only root causes, using `superpowers:systematic-debugging` for any unexpected failure.
- [ ] Document the exact local click-to-run workflow, environment variables, supported capability envelope, limitations, artifact meanings, and recovery behavior.
- [ ] Document the licensed-machine checklist: exact Sentaurus release, executable path, OS account, public verification key, TLS identity, quotas, output allowlist, authorized manuals, retention policy, and one reviewed golden run.
- [ ] Run the complete verification set:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
MYPYPATH=src .venv/bin/mypy -p tcad_agent
git diff --check
```

- [ ] Start the web app on loopback, complete the manual acceptance script in `docs/testing/pilot-acceptance.md`, and verify no secrets appear in page source, logs, or the bundle.
- [ ] On the licensed machine, run the same conformance fixture through Sentaurus and attach its signed bundle. Then run `pytest -m sentaurus tests/integration/test_cross_backend_conformance.py -q`.
- [ ] Commit with `git add README.md docs .env.example tests/e2e/test_pilot_acceptance.py && git commit -m "docs: add pilot acceptance and operations guide"`.

## Exact user acceptance sequence after implementation

1. Double-click `launch_tcad_agent.command`.
2. Confirm the browser opens the local application at `http://127.0.0.1:8765`.
3. Paste the Al / p-Si / n-Si / Al equilibrium problem from `examples/prompts/al-pn-al-equilibrium.md`.
4. Confirm the app does not invent thicknesses and asks for p-region thickness, n-region thickness, and contact treatment.
5. Enter `1 um` for each region and choose metal work-function contacts at `4.10 eV`.
6. Confirm the plan preserves 300 K, both `1e17 cm^-3` dopings, both contacts at 0 V, equilibrium only, all requested observables, Fermi statistics, mobility, SRH, Auger, and band-gap narrowing.
7. Confirm unsupported DEVSIM physics or observables are visibly marked and never silently removed. Select an allowed local approximation only if the plan explains it and requires a new approval.
8. Approve the exact plan digest and run it once. Click Run again and confirm no duplicate job is created.
9. Confirm progress shows stages rather than hidden model reasoning.
10. Inspect the validation table, technical report, canonical result, event ledger, and manifest hashes.
11. Download the bundle, rerun it through the CLI, and confirm its manifest and event-chain verification pass.
12. Switch the backend selection to Sentaurus and confirm the same portable spec compiles without editing device logic.
13. Until the licensed machine is connected, confirm execution stops with a clear `backend_unconfigured` result.
14. After licensed-machine setup, submit the signed bundle, verify the exact Sentaurus version, retrieve the signed result, and run the cross-backend conformance check.

