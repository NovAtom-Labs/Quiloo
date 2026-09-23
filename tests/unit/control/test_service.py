from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import yaml

from tcad_agent.control.models import RequestState
from tcad_agent.control.service import (
    ControlService,
    ExecutionNotApprovedError,
    PlanDigestMismatchError,
)
from tcad_agent.control.store import SqliteRequestStore
from tcad_agent.model_gateway.base import AgentProposal, ScriptedModelGateway


def proposal() -> AgentProposal:
    payload = yaml.safe_load(Path("examples/pn-junction.yaml").read_text())
    return AgentProposal(kind="spec", spec=payload)


def service(tmp_path: Path) -> ControlService:
    return ControlService(
        store=SqliteRequestStore(tmp_path / "requests.sqlite3"),
        gateway=ScriptedModelGateway((proposal(),)),
        workspace=tmp_path / "workspace",
    )


def test_approval_requires_exact_digest_and_is_idempotent(tmp_path: Path) -> None:
    control = service(tmp_path)
    submitted = control.submit("simulate the complete approved reference", backend="devsim")
    assert submitted.state is RequestState.USER_CONFIRMATION_REQUIRED
    with pytest.raises(PlanDigestMismatchError):
        control.approve(submitted.id, "wrong-digest")
    approved = control.approve(submitted.id, submitted.plan_digest or "")
    duplicate = control.approve(submitted.id, submitted.plan_digest or "")
    assert approved.state is RequestState.COMPILED
    assert duplicate == approved


def test_execution_before_approval_is_refused(tmp_path: Path) -> None:
    control = service(tmp_path)
    submitted = control.submit("simulate the complete approved reference", backend="devsim")
    with pytest.raises(ExecutionNotApprovedError):
        control.execute(submitted.id)


def test_concurrent_execution_creates_at_most_one_bundle(tmp_path: Path) -> None:
    control = service(tmp_path)
    submitted = control.submit("simulate the complete approved reference", backend="devsim")
    control.approve(submitted.id, submitted.plan_digest or "")
    with ThreadPoolExecutor(max_workers=2) as executor:
        views = tuple(executor.map(lambda _: control.execute(submitted.id), range(2)))
    final = control.get(submitted.id)
    assert final.state is RequestState.COMPLETED
    assert {view.state for view in views} <= {
        RequestState.RUNNING,
        RequestState.VALIDATING,
        RequestState.COMPLETED,
    }
    assert len(tuple((tmp_path / "workspace" / "bundles").glob("*"))) == 1
