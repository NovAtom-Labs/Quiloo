from pathlib import Path

import pytest
import yaml

from tcad_agent.domain.models import ExperimentSpec

ROOT = Path(__file__).parents[1]


@pytest.fixture
def valid_spec() -> ExperimentSpec:
    payload = yaml.safe_load((ROOT / "examples" / "pn-junction.yaml").read_text())
    return ExperimentSpec.model_validate(payload)


@pytest.fixture
def unsupported_spec(valid_spec: ExperimentSpec) -> ExperimentSpec:
    physics = valid_spec.physics.model_copy(update={"models": ("hydrodynamic",)})
    return valid_spec.model_copy(update={"physics": physics})


@pytest.fixture
def devsim_manifest():
    from tcad_agent.capabilities.models import CapabilityManifest

    return CapabilityManifest.from_backend("devsim")


@pytest.fixture
def sentaurus_manifest():
    from tcad_agent.capabilities.models import CapabilityManifest

    return CapabilityManifest.from_backend("sentaurus")
