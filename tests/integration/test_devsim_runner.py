from pathlib import Path

import pytest
import yaml

from tcad_agent.adapters.devsim.compiler import DevsimAdapter
from tcad_agent.domain.models import ExperimentSpec
from tcad_agent.runners.local import LocalRunner
from tcad_agent.runners.models import RunBudget

ROOT = Path(__file__).parents[2]
EXAMPLES = ROOT / "examples"
DEVSIM_PYTHON = Path("/Users/satyagni/Documents/NovAtom Labs/devsim/.venv/bin/python")


@pytest.mark.integration
@pytest.mark.parametrize("fixture_name", ["pn-junction.yaml", "pin-diode.yaml"])
def test_two_structures_run_through_one_backend_path(fixture_name: str, tmp_path) -> None:
    payload = yaml.safe_load((EXAMPLES / fixture_name).read_text())
    spec = ExperimentSpec.model_validate(payload)
    adapter = DevsimAdapter.from_defaults()
    job = adapter.compile(spec, tmp_path / fixture_name.removesuffix(".yaml"))
    native = LocalRunner(devsim_python=DEVSIM_PYTHON).run(job, RunBudget(seconds=120))
    result = adapter.normalize(native)
    assert result.status == "completed", native.stderr_path.read_text()
    assert result.bias_points
    assert all(point.converged for point in result.bias_points)
    assert set(result.terminals) == {"anode", "cathode"}
