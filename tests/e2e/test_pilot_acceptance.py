import hashlib
import json
import os
from pathlib import Path

import pytest
import yaml

from tcad_agent.adapters.sentaurus.compiler import SentaurusAdapter
from tcad_agent.control.models import ClarificationAnswer, RequestState, ResearchRequest
from tcad_agent.control.service import ControlService
from tcad_agent.control.store import SqliteRequestStore
from tcad_agent.domain.models import ExperimentSpec
from tcad_agent.events.ledger import EventLedger
from tcad_agent.model_gateway.base import AgentContextPacket, AgentProposal, ScriptedModelGateway
from tcad_agent.model_gateway.openhands import (
    ModelConfigurationError,
    OpenHandsBedrockGateway,
)


def test_researcher_acceptance_runs_devsim_and_compiles_same_spec_for_sentaurus(
    tmp_path: Path,
) -> None:
    prompt = Path("examples/prompts/al-pn-al-equilibrium.md").read_text()
    approximation = yaml.safe_load(
        Path("examples/al-pn-al-equilibrium-devsim.yaml").read_text()
    )
    control = ControlService(
        store=SqliteRequestStore(tmp_path / "requests.sqlite3"),
        gateway=ScriptedModelGateway(
            (AgentProposal(kind="spec", spec=approximation),)
        ),
        workspace=tmp_path / "workspace",
    )

    submitted = control.submit(prompt, backend="devsim")
    assert submitted.state is RequestState.NEEDS_CLARIFICATION
    assert {question.field for question in submitted.questions} >= {
        "geometry.p_region_thickness",
        "geometry.n_region_thickness",
        "contacts.treatment",
    }
    planned = control.answer(
        submitted.id,
        (
            ClarificationAnswer(field="geometry.p_region_thickness", value="1 um"),
            ClarificationAnswer(field="geometry.n_region_thickness", value="1 um"),
            ClarificationAnswer(
                field="contacts.treatment",
                value="explicit DEVSIM ohmic approximation for local testing",
            ),
        ),
    )
    assert planned.state is RequestState.USER_CONFIRMATION_REQUIRED
    assert planned.plan_digest
    assert planned.spec == ExperimentSpec.model_validate(approximation).normalized()

    approved = control.approve(planned.id, planned.plan_digest)
    assert approved.state is RequestState.COMPILED
    before_sentaurus_check = control.get(planned.id)
    planned_spec = ExperimentSpec.model_validate(planned.spec)
    sentaurus_job = SentaurusAdapter.from_defaults().compile(
        planned_spec, tmp_path / "sentaurus-compile"
    )
    after_sentaurus_check = control.get(planned.id)
    assert sentaurus_job.backend == "sentaurus"
    assert (tmp_path / "sentaurus-compile" / "sdevice.cmd").is_file()
    assert after_sentaurus_check.state is before_sentaurus_check.state
    assert after_sentaurus_check.revision == before_sentaurus_check.revision
    assert planned_spec.name == "al-pn-al-equilibrium-devsim-approximation"

    completed = control.execute(planned.id)
    assert completed.state is RequestState.COMPLETED
    assert completed.bundle_path is not None
    bundle = Path(completed.bundle_path)
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["backend"] == "devsim"
    assert manifest["state"] == "completed"
    for name, record in manifest["artifacts"].items():
        assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == record["sha256"]
    events = EventLedger(bundle / "events.jsonl").verify()
    assert events[-1].kind == "completed"
    assert (bundle / "report.md").is_file()
    assert (bundle / "results" / "canonical.json").is_file()


def test_full_sentaurus_example_compiles_without_a_licensed_machine(tmp_path: Path) -> None:
    spec = ExperimentSpec.model_validate(
        yaml.safe_load(Path("examples/al-pn-al-equilibrium.yaml").read_text())
    )
    job = SentaurusAdapter.from_defaults().compile(spec, tmp_path / "compiled")
    assert job.backend == "sentaurus"
    deck = job.entrypoint.read_text()
    assert "WorkFunction=4.1" in deck
    assert "Fermi" in deck
    assert "Recombination( SRH Auger )" in deck


def test_sentaurus_web_lifecycle_compiles_then_stops_as_unconfigured(
    tmp_path: Path,
) -> None:
    prompt = Path("examples/prompts/al-pn-al-equilibrium.md").read_text()
    payload = yaml.safe_load(Path("examples/al-pn-al-equilibrium.yaml").read_text())
    control = ControlService(
        store=SqliteRequestStore(tmp_path / "requests.sqlite3"),
        gateway=ScriptedModelGateway((AgentProposal(kind="spec", spec=payload),)),
        workspace=tmp_path / "workspace",
    )
    submitted = control.submit(prompt, backend="sentaurus")
    planned = control.answer(
        submitted.id,
        (
            ClarificationAnswer(field="geometry.p_region_thickness", value="1 um"),
            ClarificationAnswer(field="geometry.n_region_thickness", value="1 um"),
            ClarificationAnswer(
                field="contacts.treatment", value="metal_work_function"
            ),
        ),
    )
    approved = control.approve(planned.id, planned.plan_digest or "")
    assert approved.state is RequestState.COMPILED
    stopped = control.execute(planned.id)
    assert stopped.state is RequestState.FAILED
    assert stopped.error_code == "backend_unconfigured"


@pytest.mark.live_bedrock
def test_live_bedrock_smoke_is_opt_in_and_never_prints_key(
    pytestconfig: pytest.Config,
) -> None:
    if not pytestconfig.getoption("--run-live-bedrock"):
        pytest.skip("pass --run-live-bedrock to call the configured Bedrock model")
    token = os.getenv("AWS_BEARER_TOKEN_BEDROCK", "")
    if not token:
        pytest.skip("AWS_BEARER_TOKEN_BEDROCK is not configured")
    gateway = OpenHandsBedrockGateway.from_environment()
    try:
        proposal = gateway.propose(
            ResearchRequest(prompt="Return a structured refusal for this smoke test."),
            AgentContextPacket(),
        )
    except ModelConfigurationError as exc:
        assert token not in str(exc)
        assert "authentication or configuration failed" in str(exc)
    else:
        assert proposal.kind in {"clarification", "spec", "refusal"}
