import pytest

from tcad_agent.adapters.devsim.compiler import DevsimAdapter
from tcad_agent.domain.errors import CapabilityError
from tcad_agent.domain.models import ExperimentSpec


def test_compiler_is_deterministic_and_name_agnostic(
    valid_spec: ExperimentSpec, tmp_path
) -> None:
    adapter = DevsimAdapter.from_defaults()
    first = adapter.compile(valid_spec, tmp_path / "first")
    renamed = valid_spec.model_copy(update={"name": "arbitrary-research-structure"})
    second = adapter.compile(renamed, tmp_path / "second")
    assert first.runtime_digest == second.runtime_digest
    assert first.input_digest != second.input_digest
    assert first.entrypoint.name == "run_devsim.py"


def test_compiler_rejects_without_writing_files(
    unsupported_spec: ExperimentSpec, tmp_path
) -> None:
    workspace = tmp_path / "rejected"
    with pytest.raises(CapabilityError):
        DevsimAdapter.from_defaults().compile(unsupported_spec, workspace)
    assert not workspace.exists()
