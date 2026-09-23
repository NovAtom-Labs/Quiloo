from pathlib import Path

import yaml

from tcad_agent.adapters.devsim.compiler import DevsimAdapter
from tcad_agent.adapters.registry import BackendBinding
from tcad_agent.control.models import RequestState
from tcad_agent.control.service import ControlService
from tcad_agent.control.store import SqliteRequestStore
from tcad_agent.model_gateway.base import AgentProposal, ScriptedModelGateway
from tcad_agent.results.models import BiasPoint, CanonicalResult
from tcad_agent.runners.models import NativeRunResult


class FailedRunner:
    def run(self, job, budget) -> NativeRunResult:
        del budget
        stdout = job.entrypoint.parent / "stdout.log"
        stderr = job.entrypoint.parent / "stderr.log"
        stdout.write_text("")
        stderr.write_text("injected failure")
        return NativeRunResult(
            backend="devsim",
            status="execution_failed",
            return_code=1,
            stdout_path=stdout,
            stderr_path=stderr,
            elapsed_seconds=0.01,
            error="injected failure",
        )


class CompletedRunner:
    def run(self, job, budget) -> NativeRunResult:
        del budget
        stdout = job.entrypoint.parent / "stdout.log"
        stderr = job.entrypoint.parent / "stderr.log"
        native = job.entrypoint.parent / "native_result.json"
        stdout.write_text("")
        stderr.write_text("")
        native.write_text("{}")
        return NativeRunResult(
            backend="devsim",
            status="completed",
            return_code=0,
            stdout_path=stdout,
            stderr_path=stderr,
            result_path=native,
            elapsed_seconds=0.01,
        )


class NonconservingAdapter:
    def __init__(self) -> None:
        self.delegate = DevsimAdapter.from_defaults()

    @property
    def manifest(self):
        return self.delegate.manifest

    def compile(self, spec, workspace):
        return self.delegate.compile(spec, workspace)

    def normalize(self, native) -> CanonicalResult:
        return CanonicalResult(
            backend="devsim",
            simulator_version="2.9.1",
            status="completed",
            terminals=("anode", "cathode"),
            bias_points=(
                BiasPoint(
                    bias_v=0.0,
                    converged=True,
                    terminal_currents_a_per_m2={"anode": 1.0, "cathode": -0.5},
                ),
            ),
        )


def test_equilibrium_prompt_requires_geometry_and_contact_clarification(
    tmp_path: Path,
) -> None:
    prompt = Path("examples/prompts/al-pn-al-equilibrium.md").read_text()
    control = ControlService(
        store=SqliteRequestStore(tmp_path / "requests.sqlite3"),
        gateway=ScriptedModelGateway(()),
        workspace=tmp_path / "workspace",
    )
    view = control.submit(prompt, backend="sentaurus")
    assert view.state is RequestState.NEEDS_CLARIFICATION
    assert {question.field for question in view.questions} >= {
        "geometry.p_region_thickness",
        "geometry.n_region_thickness",
        "contacts.treatment",
    }
    assert view.spec is None


def test_devsim_request_completes_without_knowledge_index(tmp_path: Path) -> None:
    payload = yaml.safe_load(Path("examples/pn-junction.yaml").read_text())
    control = ControlService(
        store=SqliteRequestStore(tmp_path / "requests.sqlite3"),
        gateway=ScriptedModelGateway((AgentProposal(kind="spec", spec=payload),)),
        workspace=tmp_path / "workspace",
        knowledge_index=tmp_path / "missing-knowledge.sqlite3",
    )
    submitted = control.submit("simulate the complete approved reference", backend="devsim")
    assert "knowledge_index_missing" in submitted.warnings
    approved = control.approve(submitted.id, submitted.plan_digest or "")
    completed = control.execute(approved.id)
    assert completed.state is RequestState.COMPLETED
    assert completed.bundle_path is not None
    assert (Path(completed.bundle_path) / "events.jsonl").is_file()


def test_unsupported_physics_is_refused_before_approval(tmp_path: Path) -> None:
    payload = yaml.safe_load(Path("examples/pn-junction.yaml").read_text())
    payload["physics"]["models"] = ["hydrodynamic"]
    control = ControlService(
        store=SqliteRequestStore(tmp_path / "requests.sqlite3"),
        gateway=ScriptedModelGateway((AgentProposal(kind="spec", spec=payload),)),
        workspace=tmp_path / "workspace",
    )
    view = control.submit("simulate the complete unsupported request", backend="devsim")
    assert view.state is RequestState.FAILED
    assert view.error_code == "backend_unsupported"


def test_execution_failure_is_classified_and_bundled(tmp_path: Path) -> None:
    payload = yaml.safe_load(Path("examples/pn-junction.yaml").read_text())
    binding = BackendBinding(adapter=DevsimAdapter.from_defaults(), runner=FailedRunner())
    control = ControlService(
        store=SqliteRequestStore(tmp_path / "requests.sqlite3"),
        gateway=ScriptedModelGateway((AgentProposal(kind="spec", spec=payload),)),
        workspace=tmp_path / "workspace",
        backend_resolver=lambda _: binding,
    )
    submitted = control.submit("simulate complete reference", backend="devsim")
    control.approve(submitted.id, submitted.plan_digest or "")
    failed = control.execute(submitted.id)
    assert failed.state is RequestState.FAILED
    assert failed.error_code == "execution"
    assert failed.bundle_path is not None


def test_physical_validation_failure_is_not_reported_as_completed(tmp_path: Path) -> None:
    payload = yaml.safe_load(Path("examples/pn-junction.yaml").read_text())
    binding = BackendBinding(adapter=NonconservingAdapter(), runner=CompletedRunner())
    control = ControlService(
        store=SqliteRequestStore(tmp_path / "requests.sqlite3"),
        gateway=ScriptedModelGateway((AgentProposal(kind="spec", spec=payload),)),
        workspace=tmp_path / "workspace",
        backend_resolver=lambda _: binding,
    )
    submitted = control.submit("simulate complete reference", backend="devsim")
    control.approve(submitted.id, submitted.plan_digest or "")
    failed = control.execute(submitted.id)
    assert failed.state is RequestState.FAILED
    assert failed.error_code == "conservation"
